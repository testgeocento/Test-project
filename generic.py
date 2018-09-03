import sys, os, json

from osgeo import gdal, osr, ogr

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

def getDatasetFootprint(datafile):

    if datafile is None:
        print 'Missing datset'
        return None

    cols = datafile.RasterXSize
    rows = datafile.RasterYSize
    bands = datafile.RasterCount

    """Print the information to the screen. Converting the numbers returned to strings using str()"""

    print "Number of columns: " + str(cols)
    print "Number of rows: " + str(rows)
    print "Number of bands: " + str(bands)

    """First we call the GetGeoTransform method of our datafile object"""
    geoinformation = datafile.GetGeoTransform()

    """The top left X and Y coordinates are at list positions 0 and 3 respectively"""

    topLeftX = geoinformation[0]
    topLeftY = geoinformation[3]

    """Print this information to screen"""

    print "Top left X: " + str(topLeftX)
    print "Top left Y: " + str(topLeftY)

    """first we access the projection information within our datafile using the GetProjection() method. This returns a string in WKT format"""

    projInfo = datafile.GetProjection()

    """Then we use the osr module that comes with GDAL to create a spatial reference object"""

    spatialRef = osr.SpatialReference()

    """We import our WKT string into spatialRef"""

    spatialRef.ImportFromWkt(projInfo)

    """We use the ExportToProj4() method to return a proj4 style spatial reference string."""

    spatialRefProj = spatialRef.ExportToProj4()

    """We can then print them out"""

    print "WKT format: " + str(spatialRef)
    print "Proj4 format: " + str(spatialRefProj)

    gcps = datafile.GetGCPs()

    projection = ''
    if gcps is None or len(gcps) == 0:
        print('No GCPs found in file')
        geotransform = datafile.GetGeoTransform()
        projection = datafile.GetGCPProjection()
    else:
        geotransform = gdal.GCPsToGeoTransform( gcps )
        projection = datafile.GetProjection()

    if geotransform is None:
        print('Unable to extract a geotransform.')
        return None

    def toWKT(col, row):
        lng = geotransform[0] + col * geotransform[1] + row * geotransform[2]
        lat = geotransform[3] + col * geotransform[4] + row * geotransform[5]
        return str(lng) + " " + str(lat)

    wktGeometry = "POLYGON((" + toWKT(0, 0)  + ", " + toWKT(0, rows) + ", " + toWKT(cols, rows) + ", " + toWKT(cols, 0) + ", " + toWKT(0, 0) + "))"
    print "Footprint geometry " + wktGeometry + ", projection is " + projection

    footprint = ogr.CreateGeometryFromWkt(wktGeometry)

    # now make sure we have the footprint in 4326
    if projection:
        source = osr.SpatialReference(projection)
        target = osr.SpatialReference()
        target.ImportFromEPSG(4326)
        transform = osr.CoordinateTransformation(source, target)
        footprint.Transform(transform)
        print "Footprint geometry reprojected " + footprint.ExportToWkt()

    return footprint.ExportToWkt()

def getScaleParams(datafile, maxScale = None):

    if datafile is None:
        print 'No dataset provided'
        return None

    minBands = sys.maxint
    maxBands = -1 * minBands
    for band in range(datafile.RasterCount):
        band += 1
        print "[ GETTING BAND ]: ", band
        srcband = datafile.GetRasterBand(band)
        if srcband is None:
            continue

        stats = srcband.GetStatistics( True, True )
        if stats is None:
            continue

        minValue = stats[0]
        maxValue = stats[1]
        mean = stats[2]
        stddev = stats[3]
        if(minValue < minBands):
            minBands = minValue
        if(maxValue > maxBands):
            maxBands = maxValue

        print "[ STATS ] =  Minimum=%.3f, Maximum=%.3f, Mean=%.3f, StdDev=%.3f" % ( \
            stats[0], stats[1], stats[2], stats[3] )


    print "Min bands is " + str(minBands) + " and max bands is " + str(maxBands)

    print "Starting value stretching"

    scaleParams = []
    exponents = []
    for band in range(datafile.RasterCount):
        band += 1
        srcband = datafile.GetRasterBand(band)
        dataType = srcband.DataType
        if maxScale is None:
            if dataType == 1:
                maxScale = 256
            elif dataType == 2:
                maxScale = 65535
            else:
                maxScale = 256
        scaleParams.append([minBands, maxBands, 0, maxScale])
        exponents.append(0.5)

    print "Scale value is " + str(scaleParams)

    return scaleParams;
