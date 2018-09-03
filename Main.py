""" the osgeo package contains the GDAL, OGR and OSR libraries """

""" for python 2 and python 3 execution exec(open("./path/to/script.py").read(), globals()) """

import sys, os, json

from osgeo import gdal, osr, ogr

sys.path.append('/usr/bin/')
import gdal_merge
import gdal_pansharpen

import generic

def Usage():
    print('Usage: trueColour(args)')

def trueColour(argv):
    
    # TODO - use gdal.GeneralCmdLineProcessor( argv ) instead
    inputdirectory = sys.argv[1]
    outputdirectory = sys.argv[2]
    platformname = sys.argv[3]
    producttype = sys.argv[4]
    if len(sys.argv) == 6:
        aoiwkt = sys.argv[5]

    if platformname == 'SENTINEL2':
        # find SAFE directory
        for file in os.listdir(inputdirectory):
            filePath = inputdirectory + file
            print filePath
            if os.path.isdir(filePath) and filePath.endswith(".SAFE"):
                safeDirectory = filePath
                break
        if safeDirectory is None:
            sys.exit("Could not find SAFE directory")
        # retrieve the tiff file now
        descriptorPath = safeDirectory + "/MTD_MSIL1C.xml"
        print "Opening dataset " + descriptorPath
        ds = gdal.Open(descriptorPath)

        footprintGeometryWKT = ds.GetMetadataItem("FOOTPRINT")
        print "FOOTPRINT: " + footprintGeometryWKT

        subdatasets = ds.GetMetadata_List("SUBDATASETS")
        for subdataset in subdatasets:
            if ":TCI:" in subdataset:
                tciFileName = subdataset.split("=")[1]
                break
        if tciFileName is None:
            sys.exit("Could not find true colour image in subdatasets")

        print "TCI file name " + tciFileName

        tciDs = gdal.Open(tciFileName)

        fileList = tciDs.GetFileList()

        for fileName in fileList:
            if fileName.endswith("_TCI.jp2"):
                jp2FilePath = fileName

        if jp2FilePath is None:
            sys.exit("Could not find jp2 file for true colour image")

        # no delete method available
        #ds.delete();
        #tciDs.delete();

        tciDs = gdal.Open(jp2FilePath)

        intersectionWKT = calculateCutline(footprintGeometryWKT, aoiwkt)

        csvFileDirectory = inputdirectory
        csvFilePath = createCutline(csvFileDirectory, intersectionWKT)

        warpedDs = executeWarp(tciDs, csvFilePath)

        tempFilePath = outputdirectory + '/temp.tiff';
        ds = gdal.Translate(tempFilePath, warpedDs, format = 'GTiff')
        executeOverviews(ds)
        outputFilePath = outputdirectory + '/productOutput.tiff'
        ds = gdal.Translate(outputFilePath, ds, format = 'GTiff')

        # a bit of clean up
        os.remove(tempFilePath)

        if intersectionWKT is None:
            productFootprintWKT = footprintGeometryWKT
        else:
            productFootprintWKT = intersectionWKT

        # now write the output json file
        product = {
            "name": "True colour image",
            "productType": "COVERAGE",
            "SRS":"EPSG:4326",
            "envelopCoordinatesWKT": productFootprintWKT,
            "filePath": outputFilePath,
            "description": "True colour image from Sentinel2 platform"
        }
        writeOutput(outputdirectory, "True colour generation using geocento process", [product])

        print "True Colour script finished for SENTINEL2 product(s) at " + inputdirectory

    elif platformname == 'LANDSAT8':
        bandFiles = []
        # get the required bands
        for file in os.listdir(inputdirectory):
            filePath = inputdirectory + file
            print filePath
            if filePath.upper().endswith("_B2.TIF") or \
                    filePath.upper().endswith("_B3.TIF") or \
                    filePath.upper().endswith("_B4.TIF"):
                bandFiles.append(filePath)
            elif filePath.upper().endswith("_B8.TIF"):
                band8FilePath = filePath

        if len(bandFiles) != 3 or band8FilePath is None:
            sys.exit("Missing bands in Landsat8 directory")

        # make sure the bands are arranged in the right order
        bandFiles = sorted(bandFiles, reverse = True)

        # now merge into one file
        mergeFilePath = outputdirectory + '/merge.tiff';
        sys.argv = ['/usr/bin/gdal_merge.py', '-separate', '-o', mergeFilePath]
        sys.argv.extend(bandFiles)
        print sys.argv
        gdal_merge.main()

        if not os.path.exists(mergeFilePath):
            sys.exit("Merge failed")

        # pan sharpen the image
        panSharpenFilePath = outputdirectory + '/pansharpen.tiff';
        sys.argv = ['/usr/bin/gdal_pansharpen.py', '-nodata', '0', band8FilePath, mergeFilePath, panSharpenFilePath]
        print sys.argv
        gdal_pansharpen.main()

        if not os.path.exists(panSharpenFilePath):
            sys.exit("Pansharpen failed")

        # stretch the values
        ds = gdal.Open(panSharpenFilePath)
        footprintGeometryWKT = generic.getDatasetFootprint(ds)
        print "FOOTPRINT: " + footprintGeometryWKT

        intersectionWKT = generic.calculateCutline(footprintGeometryWKT, aoiwkt)

        csvFileDirectory = outputdirectory
        csvFilePath = generic.createCutline(csvFileDirectory, intersectionWKT)

        warpedDs = executeWarp(ds, csvFilePath)

        tempFilePath = outputdirectory + '/temp.tiff';
        scaleParams = generic.getScaleParams(warpedDs, 255)
        print scaleParams
        ds = gdal.Translate(tempFilePath, warpedDs, scaleParams = scaleParams, exponents = [0.5, 0.5, 0.5], format = 'GTiff')
        executeOverviews(ds)
        outputFilePath = outputdirectory + '/productOutput.tiff'
        ds = gdal.Translate(outputFilePath, ds, outputType = gdal.GDT_Byte, format = 'GTiff')

        # a bit of clean up
        os.remove(mergeFilePath)
        os.remove(panSharpenFilePath)
        os.remove(tempFilePath)

        if intersectionWKT is None:
            productFootprintWKT = footprintGeometryWKT
        else:
            productFootprintWKT = intersectionWKT

        # now write the output json file
        product = {
            "name": "True colour image",
            "productType": "COVERAGE",
            "SRS":"EPSG:4326",
            "envelopCoordinatesWKT": productFootprintWKT,
            "filePath": outputFilePath,
            "description": "True colour image from Landsat 8 platform"
        }
        writeOutput(outputdirectory, "True colour generation using geocento process", [product])

        print "True Colour script finished for LANDSAT8 STANDARD product(s) at " + inputdirectory

    elif platformname == 'LANDSAT7':
        bandFiles = []
        # get the required bands
        for file in os.listdir(inputdirectory):
            filePath = inputdirectory + file
            print filePath
            if filePath.upper().endswith("_B1.TIF") or \
                    filePath.upper().endswith("_B2.TIF") or \
                    filePath.upper().endswith("_B3.TIF"):
                bandFiles.append(filePath)
            elif filePath.upper().endswith("_B8.TIF"):
                band8FilePath = filePath

        if len(bandFiles) != 3 or band8FilePath is None:
            sys.exit("Missing bands in Landsat8 directory")

        # make sure the bands are arranged in the right order
        bandFiles = sorted(bandFiles, reverse = True)

        # now merge into one file
        mergeFilePath = outputdirectory + '/merge.tiff';
        sys.argv = ['/usr/bin/gdal_merge.py', '-separate', '-o', mergeFilePath]
        sys.argv.extend(bandFiles)
        print sys.argv
        gdal_merge.main()

        if not os.path.exists(mergeFilePath):
            sys.exit("Merge failed")

        # pan sharpen the image
        panSharpenFilePath = outputdirectory + '/pansharpen.tiff';
        sys.argv = ['/usr/bin/gdal_pansharpen.py', '-nodata', '0', band8FilePath, mergeFilePath, panSharpenFilePath]
        print sys.argv
        gdal_pansharpen.main()

        if not os.path.exists(panSharpenFilePath):
            sys.exit("Pansharpen failed")

        # stretch the values
        ds = gdal.Open(panSharpenFilePath)
        footprintGeometryWKT = generic.getDatasetFootprint(ds)
        print "FOOTPRINT: " + footprintGeometryWKT

        intersectionWKT = generic.calculateCutline(footprintGeometryWKT, aoiwkt)

        csvFileDirectory = outputdirectory
        csvFilePath = generic.createCutline(csvFileDirectory, intersectionWKT)

        warpedDs = executeWarp(ds, csvFilePath)

        tempFilePath = outputdirectory + '/temp.tiff';
        scaleParams = generic.getScaleParams(warpedDs, 255)
        print scaleParams
        ds = gdal.Translate(tempFilePath, warpedDs, scaleParams = scaleParams, exponents = [0.5, 0.5, 0.5], format = 'GTiff')
        executeOverviews(ds)
        outputFilePath = outputdirectory + '/productOutput.tiff'
        ds = gdal.Translate(outputFilePath, ds, outputType = gdal.GDT_Byte, noData = 0, format = 'GTiff')

        # a bit of clean up
        os.remove(mergeFilePath)
        os.remove(panSharpenFilePath)
        os.remove(tempFilePath)

        if intersectionWKT is None:
            productFootprintWKT = footprintGeometryWKT
        else:
            productFootprintWKT = intersectionWKT

        # now write the output json file
        product = {
            "name": "True colour image",
            "productType": "COVERAGE",
            "SRS":"EPSG:4326",
            "envelopCoordinatesWKT": productFootprintWKT,
            "filePath": outputFilePath,
            "description": "True colour image from Landsat 7 platform"
        }
        writeOutput(outputdirectory, "True colour generation using geocento process", [product])

        print "True Colour script finished for LANDSAT7 STANDARD product(s) at " + inputdirectory

    elif platformname == 'TRIPPLESAT' or platformname == 'DEIMOS-2':
        # get the tif files
        tifFiles = findFiles(inputdirectory, 'tif')

        if len(tifFiles) == 0:
            sys.exit("Missing TIFF file in directory")

        tifFile = tifFiles[0]

        # create overlays and extract footprint
        ds = gdal.Open(tifFile)
        # reproject to 4326
        tempFilePath = outputdirectory + '/temp.tiff';
        ds = gdal.Warp(tempFilePath, ds, format = 'GTiff', dstSRS = 'EPSG:4326')
        productFootprintWKT = generic.getDatasetFootprint(ds)
        print "FOOTPRINT: " + productFootprintWKT
        executeOverviews(ds)
        outputFilePath = outputdirectory + '/productOutput.tiff'
        ds = gdal.Translate(outputFilePath, ds, bandList = [1,2,3], outputType = gdal.GDT_Byte, noData = 0, format = 'GTiff')

        # now write the output json file
        product = {
            "name": "True colour image",
            "productType": "COVERAGE",
            "SRS":"EPSG:4326",
            "envelopCoordinatesWKT": productFootprintWKT,
            "filePath": outputFilePath,
            "description": "True colour image from TrippleSat platform"
        }
        
        writeOutput(outputdirectory, "True colour generation using geocento process", [product])

        print "True Colour script finished for TRIPPLE SAT product(s) at " + inputdirectory

    elif platformname == 'PLANETSCOPE':
        # get the tif files
        tifFiles = findFiles(inputdirectory, 'tif')

        if len(tifFiles) == 0:
            sys.exit("Missing TIFF file in directory")

        for file in tifFiles:
            if not file.lower().endswith("_udm_clip.tif"):
                tifFile = file
                break
        # check if visual or analytics
        analytic = "Analytic" in tifFile

        # create overlays and extract footprint
        ds = gdal.Open(tifFile)
        # reproject to 4326
        tempFilePath = outputdirectory + '/temp.tiff';
        outputFilePath = outputdirectory + '/productOutput.tiff'
        # reduce bands if needed
        ds = gdal.Translate('temp', ds, format = 'MEM', bandList = [1,2,3])
        # if analytics we need to do some scaling for contrasts
        if analytic:
            print "Analytic product, modifying contrast for visualisation"
            scaleParams = generic.getScaleParams(ds, 255)
            print "Scale params "
            print(scaleParams)
            ds = gdal.Translate('temp', ds, format = 'MEM', scaleParams = scaleParams, exponents = [0.5, 0.5, 0.5])
        ds = gdal.Warp('temp', ds, format = 'GTiff', srcNodata = 0, dstAlpha = True, dstSRS = 'EPSG:4326')
        productFootprintWKT = generic.getDatasetFootprint(ds)
        print "FOOTPRINT: " + productFootprintWKT
        ds = gdal.Translate(tempFilePath, ds, outputType = gdal.GDT_Byte, format = 'GTiff')
        executeOverviews(ds)
        ds = gdal.Translate(outputFilePath, ds, format = 'GTiff')
    
        # now write the output json file
        product = {
            "name": "True colour image",
            "productType": "COVERAGE",
            "SRS":"EPSG:4326",
            "envelopCoordinatesWKT": productFootprintWKT,
            "filePath": outputFilePath,
            "description": "True colour image from TrippleSat platform"
        }
        
        writeOutput(outputdirectory, "True colour generation using geocento process", [product])

        print "True Colour script finished for TRIPPLE SAT product(s) at " + inputdirectory

    elif platformname == 'SENTINEL1':
        pass
    else:
        sys.exit("Unknown platform " + platformname)

def findFiles(directory, extension):
    print "scanning directory " + directory + " for files with extension " + extension
    foundFiles = []
    for dirpath, dirnames, files in os.walk(directory):
        for name in files:
            print "file " + name
            if name.lower().endswith(extension):
                print "Adding file " + name + " at " + dirpath
                foundFiles.append(os.path.join(dirpath, name))
    return foundFiles

def executeWarp(ds, cutlineFilePath):
    return gdal.Warp('temp', ds, format = 'MEM', cutlineDSName = cutlineFilePath, cropToCutline = True, dstSRS = 'EPSG:4326')

def calculateCutline(footprintGeometryWKT, aoiWKT):
    # calculate intersection
    if aoiWKT is None:
        print "No intersection provided!"
        return

    aoiGeometry = ogr.CreateGeometryFromWkt(aoiWKT)
    footprintGeometry = ogr.CreateGeometryFromWkt(footprintGeometryWKT)

    intersectionGeometry = footprintGeometry.Intersection(aoiGeometry)
    if intersectionGeometry is None:
        return

    return intersectionGeometry.ExportToWkt()


def createCutline(directory, footprintGeometryWKT, aoiWKT):
    createCutline(directory, calculateCutline(footprintGeometryWKT, aoiWKT))

def createCutline(directory, intersectionWKT):
    if intersectionWKT is None:
        return

    csvFileName = directory + '/cutline.csv'
    csvFile = open(csvFileName, 'w')
    csvFile.write('ID, WKT\n')
    csvFile.write('1, "' + intersectionWKT + '"\n')
    csvFile.close()
    prjFile = open(directory + '/cutline.prj', 'w')
    prjFile.write('EPSG:4326')
    prjFile.close()

    return csvFileName


def executeOverviews(ds):
    # TODO - calculate based on the size of the image
    overviewList = [2, 4, 8, 16, 32]
    ds.BuildOverviews( "NEAREST", overviewList)

def writeOutput(directory, message, products):
    outputValues = {
        "message": message,
        "products": products
    }
    with open(directory + '/output.json', 'w') as outfile:
        json.dump(outputValues, outfile)

def main():
    return trueColour(sys.argv)

if __name__ == '__main__':
    sys.exit(trueColour(sys.argv))
