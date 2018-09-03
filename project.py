""" the osgeo package contains the GDAL, OGR and OSR libraries """

""" for python 2 and python 3 execution exec(open("./path/to/script.py").read(), globals()) """

import sys, os
from osgeo import gdal, osr, ogr

#import ('/usr/bin/gdal_pansharpen')

gdal_pansharpen()

""" create a gdal object and open the "landsatETM.tif" file """

filename = sys.argv[1]
datafile = gdal.Open(filename)

if datafile is None:
    print 'Could not find file ' + filename
    sys.exit()

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
    print('No GCPs found on file ' + filename)
    geotransform = datafile.GetGeoTransform()
    projection = datafile.GetGCPProjection()
else:
    geotransform = gdal.GCPsToGeoTransform( gcps )
    projection = datafile.GetProjection()

if geotransform is None:
    print('Unable to extract a geotransform.')
    sys.exit( 1 ) 
                                
print(geotransform[1])
print(geotransform[4])
print(geotransform[2])
print(geotransform[5])

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

intersectionWkt = None
requestWkt = sys.argv[2]
if requestWkt is None:
    print "No intersection provided!"
    intersectionWkt = footprint
else:
    request = ogr.CreateGeometryFromWkt(requestWkt)
    intersection = footprint.Intersection(request)
    intersectionWkt = intersection.ExportToWkt()

print 'Intersection WKT of ' + request.ExportToWkt() + ' with ' + footprint.ExportToWkt() + ' is ' + intersectionWkt

#quit()

directory = os.path.dirname(filename)
print "Path is " + directory

csvFile = open(directory + '/cutline.csv', 'w')
csvFile.write('ID, WKT\n')
csvFile.write('1, "' + intersectionWkt + '"\n')
csvFile.close()
prjFile = open(directory + '/cutline.prj', 'w')
prjFile.write('EPSG:4326')
prjFile.close()

tmp_ds = gdal.Warp('temp', filename, format = 'MEM', cutlineDSName = directory + '/cutline.csv', cropToCutline = True, dstSRS = 'EPSG:4326')
gdal.Translate(directory + '/out.tiff', tmp_ds, format = 'GTiff')
# , photometric = 'RGB')

