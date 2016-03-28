#!python

import sys
import getopt
import re
from svg.path import Path, Line, Arc, CubicBezier, QuadraticBezier, parse_path
from xml.dom import minidom
import numpy as np
import math
from shapely.geometry import LinearRing
from matplotlib import pyplot as plt
from pprint import pprint


def generateInfil(lineRing, penRadius, maxIterations, side='right'):
    if maxIterations == 0:
        return []
    try:
        offset = lineRing.parallel_offset(penRadius, side, join_style=2)
    except:
        pass
    parts = hasattr(offset, 'geoms') and offset or [offset]
    length = 0
    for p in parts:
        length += p.length
    if length > lineRing.length:
        try:
            offset = lineRing.parallel_offset(penRadius, 'left', join_style=2)
        except:
            pass
        parts = hasattr(offset, 'geoms') and offset or [offset]
    subparts = []
    for p in parts:
        subparts.append(p)
        subparts += generateInfil(p, penRadius, maxIterations=maxIterations-1, side='right')
    return subparts
def generatePathes(borderNodes, penRadius, maxIterations=2):
    l = LinearRing(borderNodes)
    offsets = generateInfil(l, penRadius,maxIterations)
    return [l] + offsets
def genGCode(path, zDraw, zMove, xOffset, yOffset, zOffset):
    code = []
    code += 'G1 Z'+str(zMove + zOffset)+';\n'
    code += 'G1 X'+str(path[0][0]+xOffset)+' Y'+str(path[0][1]+yOffset)+';\n'
    code += 'G1 Z'+str(zDraw + zOffset)+';\n'
    for p in path[1:]:
        code += 'G1 X'+str(p[0]+xOffset)+' Y'+str(p[1]+yOffset)+';\n'
    code += 'G1 Z'+str(zMove + zOffset)+';\n'
    return code


def main(argv):
    zDraw = -0.1
    zMove = 1.0
    xOffset = 0.0
    yOffset = 0.0
    zOffset = 0.0
    userScale = 1.0
    feed = 500
    penRadius = 0.09
    #-s 0.3533 -x 20 -y 20 -z 4.5 -f 500

    helpString = 'svg2penGcode.py <inputfile>'
    try:
        opts, args = getopt.getopt(argv[:-1],"hp:d:m:x:y:z:s:f:",["help", "pen-radius=", "draw=", "move=", "x-offset=", "y-offset", "z-offset", "scale=", "feed="])
    except getopt.GetoptError:
        print helpString
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print helpString
            sys.exit(0)
        elif opt in ("-p", "--pen-radius"):
            penRadius = float(arg)
        elif opt in ("-d", "--draw"):
            zDraw = float(arg)
        elif opt in ("-m",   "--move"):
            zMove = float(arg)
        elif opt in ("-x", "--x-offset"):
            xOffset = float(arg)
        elif opt in ("-y", "--y-offset"):
            yOffset = float(arg)
        elif opt in ("-z", "--z-offset"):
            zOffset = float(arg)
        elif opt in ("-s", "--scale"):
            userScale = float(arg)
        elif opt in ("-f", "--feed"):
            feed = float(arg)
    

    fileName = sys.argv[-1]

    doc = minidom.parse(fileName)
    pathstrings = [path.getAttribute('d') for path in doc.getElementsByTagName('path')]

    r = re.compile('M([-+]?[0-9]*\.?[0-9]*)\s([-+]?[0-9]*\.?[0-9]*)\s')
    tmp = pathstrings
    pathstrings = []
    for path in tmp:
        pos = path.find('z m')
        if pos > 0:
            paths = path.split('z m')
            paths[0] += 'z'
            sb = r.search(paths[0])
            base = [float(sb.group(1)), float(sb.group(2))]
            for i in range(1, len(paths)):
                paths[i] = 'M' + paths[i]
                sr = r.search(paths[i])
                rel = [float(sr.group(1)), float(sr.group(2))]
                rr = re.compile('M([-+]?[0-9]*\.?[0-9]*\s[-+]?[0-9]*\.?[0-9]*)')
                ss = rr.search(paths[i])
                paths[i] = paths[i].replace(ss.group(1), str(base[0]+rel[0]) + ' ' + str(base[1]+rel[1]))
            pathstrings.append(paths)
        else:
            pathstrings.append([path])

    transform = doc.getElementsByTagName('g')[0].getAttribute('transform')
    rt = re.compile('translate\(([-+]?[0-9]*\.?[0-9]*,[-+]?[0-9]*\.?[0-9]*)\)')
    rs = re.compile('scale\(([-+]?[0-9]*\.?[0-9]*,[-+]?[0-9]*\.?[0-9]*)\)')
    st = rt.search(transform)
    ss = rs.search(transform)

    translate = [float(val) for val in st.group(1).split(',')]
    scale     = [float(val) for val in ss.group(1).split(',')]


    r = re.compile('([mMcClL]?[-+]?[0-9]*\.?[0-9]*\s[-+]?[0-9]*\.?[0-9]*[z\s^]?)')
    rs = re.compile('([-+]?[0-9]*\.?[0-9]*)[\s,]([-+]?[0-9]*\.?[0-9]*?)')
    rsf = re.compile('([-+]?[0-9]*\.?[0-9]*[\s,][-+]?[0-9]*\.?[0-9]*?)')

    correctedPaths = []
    for paths in pathstrings:
        correctedPaths.append([])
        for path in paths:
            descriptions = r.findall(path)
            for i in range(len(descriptions)):
                s = rs.search(descriptions[i])
                sf = rsf.search(descriptions[i])
                vals = [float(val) for val in [s.group(1), s.group(2)] ]
                vals[0] *= scale[0]
                vals[1] *= -scale[1]
                if i == 0:
                    vals[0] += translate[0]
                    vals[1] += translate[1]
                vals[0] *= userScale
                vals[1] *= userScale
                if i == 0:
                    vals[0] += xOffset
                    vals[1] += yOffset
                descriptions[i] = descriptions[i].replace(sf.group(1), str(vals[0]) + ' ' + str(vals[1]))
            correctedPaths[-1].append(''.join(descriptions))

    paths = []
    pathsNodes = []
    minX = 1e10
    minY = 1e10
    for cPaths in correctedPaths:
        paths.append([])
        pathsNodes.append([])
        for c in cPaths:
            p = parse_path(c)
            paths[-1].append(p)
            pathsNodes[-1].append([])
            # for subPath in paths[-1]:
            aggL = 0
            length = p.length()
            numCheck = int(length/penRadius*9.9)
            if length > 0:
                checkPoints = [p.point(cl) for cl in np.arange(0, 1, 1.0/numCheck)]
                minX = min([minX, min([p.real for p in checkPoints ])])
                minY = min([minY, min([p.imag for p in checkPoints ])])
                index = 1
                while index < len(checkPoints):
                    aggL += abs(checkPoints[index] - checkPoints[index-1])
                    if aggL > penRadius or aggL == 0:
                        pathsNodes[-1][-1].append([checkPoints[index].real, checkPoints[index].imag])
                        aggL = 0
                    index += 1
    print minX, minY
    tmp = pathsNodes
    pathsNodes = []
    for pp in tmp:
        pathsNodes.append([])
        for p in pp:
            pathsNodes[-1].append([])
            for n in p:
                pathsNodes[-1][-1].append([n[0] - minX, n[1] - minY])

    code = []
    code.append('G21;\nG90;\nG28 X0 Y0;\nG28 Z0;\nG1 F' + str(feed) + ';\n')
    code.append('G1 Z' + str(zMove + zOffset) + ';\n')
    for nodesGroup in pathsNodes:
        if len(nodesGroup) > 1:
            maxIter = 0
        else:
            maxIter = 6
        for nodes in nodesGroup:
            offsets = generatePathes(nodes, penRadius, maxIterations=maxIter)
            for offset in offsets:
                try:
                    x,y = offset.xy
                    nodes = zip(x, y)
                    code += genGCode(nodes, zDraw, zMove, xOffset, yOffset, zOffset)
                except:
                    print offset
    code.append('G28 X0;\n')
    code.append('G1 Y180;\n')
    code.append('M84;\n;\n;\n')
    f = open(fileName+'.gcode', 'w')
    f.writelines(code)
    f.close()



if __name__ == "__main__":
    main(sys.argv[1:])

