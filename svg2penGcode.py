#!python

import sys
import getopt
import re
from svg.path import Path, Line, Arc, CubicBezier, QuadraticBezier, parse_path
from xml.dom import minidom
import numpy as np
import math
from shapely.geometry import LinearRing
from pprint import pprint


def formatVal(val, f="%0.2f"):
    return (f % (val))
def generateInfil(lineRing, penRadius, minPenRadius, maxIterations, side='left', join_style=2):
    if penRadius < minPenRadius:
        penRadius = minPenRadius
    if maxIterations == 0:
        return []
    try:
        offset = lineRing.parallel_offset(penRadius, side, join_style=join_style, mitre_limit=10)
    except:
        return []
    parts = hasattr(offset, 'geoms') and offset or [offset]
    # Check if infil generated in right side. If not bounds of infil will be wider than bounds of original
    minX = minY = 1e10
    maxX = maxY = -1e10
    for p in parts:
        try:
            x, y = p.xy
            minX = min(minX, min(x))
            minY = min(minY, min(y))
            maxX = max(maxX, max(x))
            maxY = max(maxY, max(y))
        except:
            # print(p)
            pass
    try:
        ox, oy = lineRing.xy
        if minX < min(ox) or minY < min(oy) or maxX > max(ox) or maxY > max(oy):
            # Make with right side
            try:
                offset = lineRing.parallel_offset(penRadius, 'right', join_style=join_style, mitre_limit=10)
            except:
                pass
            parts = hasattr(offset, 'geoms') and offset or [offset]
    except:
        pass
    # for i in range(len(parts)):
    #     try:
    #         x,y = parts[i].xy
    #         nodes = zip(x, y)
    #         parts[i] = LinearRing(nodes)
    #     except:
    #         pass
    subparts = []
    for p in parts:
        subparts.append(p)
        subparts += generateInfil(p, penRadius/2.5, minPenRadius, maxIterations=maxIterations-1, side='left',join_style=join_style)
    return subparts
def generatePathes(borderNodes, penRadius, minPenRadius, maxIterations=2, includeBorder=False, insideFirst=False, jointStyle=2):
    l = LinearRing(borderNodes)
    offsets = generateInfil(l, penRadius, minPenRadius, maxIterations,join_style=jointStyle)
    if len(offsets) == 0:
        raise RuntimeError("No infil generated (")
    if includeBorder:
        paths = [l] + offsets
    else:
        paths =  offsets
    if insideFirst:
        return list(reversed(paths))
    else:
        return paths
def pathLength(path):
    length = 0
    for ct in range(len(path)-1):
        length += math.sqrt( (path[ct+1][0] -  path[ct][0])**2.0 + (path[ct+1][1] -  path[ct][1])**2.0 )
    return length
def genGCode(path, zDraw, zMove, xOffset, yOffset, zOffset, drawSpeed, moveSpeed, zMoveSpeed):
    code = []
    #code += 'G1 Z'+formatVal(zMove + zOffset)+';\n'
    code += '\n;****************************************************************\n'
    code += 'G1 X'+formatVal(path[0][0]+xOffset)+' Y'+formatVal(path[0][1]+yOffset)+' F'+formatVal(moveSpeed)+';\n'
    code += 'G1 Z'+formatVal(zDraw + zOffset)+' F'+formatVal(zMoveSpeed)+';\nG1 F' + formatVal(drawSpeed) + ';\n'
    for p in path[1:]:
        code += 'G1 X'+formatVal(p[0]+xOffset)+' Y'+formatVal(p[1]+yOffset)+';\n'
    code += 'G1 Z'+formatVal(zMove + zOffset)+';\n'
    return code
def printProgress (iteration, total, prefix = '', suffix = '', decimals = 2, barLength = 100):
    filledLength    = int(round(barLength * iteration / float(total)))
    percents        = round(100.00 * (iteration / float(total)), decimals)
    bar             = '#' * filledLength + '-' * (barLength - filledLength)
    sys.stdout.write('%s [%s] %s%s %s\r' % (prefix, bar, percents, '%', suffix)),
    sys.stdout.flush()
    if iteration == total:
        print("\n")


def main(argv):
    zDraw = -0.1
    zMove = 1.0
    xOffset = 0.0
    yOffset = 0.0
    zOffset = 1.0
    zApproach = 10
    zRetreat = 10
    userScale = 1.0
    feed = 500
    moveFeed = 1000
    zMoveFeed = 120
    penRadius = 0.19
    minPenRadius = 0.1
    includeBorder = False
    numRepeatFirst = 3
    makeSetupFile = False
    insideFirst = False
    #Possible 1, 2, 3
    jointStyle = 1;
    maxInfilIterations = 50;
    mirrored = False
    #-s 0.3533 -x 20 -y 20 -z 4.5 -f 500

    helpString = 'svg2penGcode.py [options] <inputfile[s]>'
    try:
        opts, args = getopt.getopt(argv,"hp:d:m:x:y:z:s:f:b",["help",
            "pen-radius=", "min-pen-radius=", "draw=", "move=",
            "x-offset=", "y-offset=", "z-offset=", "scale=", "mirrored",
            "feed=", "feed-move=",
            "border", "repeat=", "inside-first",
            "join-style=", "max-iterations=",
            "setup"])
    except getopt.GetoptError:
        print helpString
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print helpString
            sys.exit(0)
        elif opt in ("-p", "--pen-radius"):
            penRadius = float(arg)
        elif opt in ("--min-pen-radius"):
            minPenRadius = float(arg)
        elif opt in ("-d", "--draw"):
            zDraw = float(arg)
        elif opt in ("-m", "--move"):
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
        elif opt in ("--feed-move"):
            feedMove = float(arg)
        elif opt in ("-b", "--border"):
            includeBorder = True
        elif opt in ("--repeat"):
            numRepeatFirst = int(arg)
        elif opt in ("--inside-first"):
            insideFirst = True
        elif opt in ("--join-style"):
            jointStyle = int(arg)
        elif opt in ("--max-iterations"):
            maxInfilIterations = int(arg)
        elif opt in ("--setup"):
            makeSetupFile = True
        elif opt in ("--mirrored"):
            mirrored = True
    
    correctedPaths = []
    for fileName in args:
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
    maxX = -1e10
    maxY = -1e10
    count = 0
    for cPaths in correctedPaths:
        printProgress(count, len(correctedPaths), prefix='Parsing')
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
            if length > 1:
                checkPoints = [p.point(cl) for cl in np.arange(0, 0.999, 1.0/numCheck)]
                minX = min([minX, min([p.real for p in checkPoints ])])
                minY = min([minY, min([p.imag for p in checkPoints ])])
                maxX = max([maxX, max([p.real for p in checkPoints ])])
                maxY = max([maxY, max([p.imag for p in checkPoints ])])
                index = 1
                while index < len(checkPoints):
                    aggL += abs(checkPoints[index] - checkPoints[index-1])
                    if aggL > penRadius or aggL == 0:
                        pathsNodes[-1][-1].append([checkPoints[index].real, checkPoints[index].imag])
                        aggL = 0
                    index += 1
        count += 1
    printProgress(1, 1, prefix='Parsing', suffix='Done')
    tmp = pathsNodes
    pathsNodes = []
    for pp in tmp:
        pathsNodes.append([])
        for p in pp:
            pathsNodes[-1].append([])
            for n in p:
                x = n[0]
                y = n[1]
                if mirrored:
                    x = minX + maxX - x
                    pathsNodes[-1][-1].append([y - minY, maxX - x])
                else:
                    pathsNodes[-1][-1].append([x - minX, y - minY])

    code = []
    code.append('G21;\nG90;\nG28 X0 Y0;\nG28 Z0;\n')
    code.append('G1 Z' + formatVal(zMove + zOffset + zApproach) + ';\n')
    count = 0
    for nodesGroup in pathsNodes:
        printProgress(count, len(pathsNodes), prefix='Generating')
        if len(nodesGroup) > 1:
            maxIter = 1
        else:
            maxIter = maxInfilIterations
        for nodes in nodesGroup:
            offsets = generatePathes(nodes, penRadius, maxIterations=maxIter, includeBorder=includeBorder, minPenRadius=minPenRadius, insideFirst=insideFirst, jointStyle=jointStyle)
            if len(offsets) > numRepeatFirst:
                offsets = [offsets[:numRepeatFirst]] + offsets
            else:
                offsets = offsets + offsets
            for offset in offsets:
                try:
                    x,y = offset.xy
                    nodes = zip(x, y)
                    if pathLength(nodes) > 1:
                        code += genGCode(nodes, zDraw, zMove, xOffset, yOffset, zOffset, feed, moveFeed, zMoveFeed)
                except:
                    # print offset
                    pass
        count += 1
    code.append('G1 Z' + formatVal(zMove + zOffset + zRetreat) + ';\n')
    code.append('G28 X0;\n')
    code.append('M84;\n;')
    f = open(fileName+'.gcode', 'w')
    f.writelines(code)
    f.close()
    printProgress(1, 1, prefix='Generating', suffix='Done')
    print 'PCB size ', formatVal(maxX - minX, f="%0.f"), formatVal(maxY - minY, f="%0.f")

    if makeSetupFile:
        #Gen code for point pen to minX minY position with z offset 
        code = []
        code.append('G21;\nG90;\nG28 X0 Y0;\nG28 Z0;\n')
        code.append('G1 Z' + formatVal(zMove + zOffset + zApproach) + ';\n')
        code.append('G1 X'+formatVal(xOffset)+' Y'+formatVal(yOffset)+' F'+formatVal(moveFeed)+';\n')
        #This privents strange movement as the end
        code.append('G1 X'+formatVal(xOffset+0.1)+' Y'+formatVal(yOffset+0.1)+';\n')
        code.append('G1 X'+formatVal(xOffset)+' Y'+formatVal(yOffset)+';\n')
        code.append('G1 Z' + formatVal(zOffset) + ';\n')
        code.append('M84;\n;')
        f = open(fileName+'.setup.gcode', 'w')
        f.writelines(code)
        f.close()
        #Gen code for mark corners
        stroke = 2.0;
        cornerNodes = []
        cornerNodes.append([])
        cornerNodes[-1].append([[0.0, 0.0 + stroke], [0.0, 0.0], [0.0 + stroke, 0.0]])
        cornerNodes.append([])
        cornerNodes[-1].append([[(maxX-minX) - stroke, 0.0], [(maxX-minX), 0.0], [(maxX-minX), 0.0 + stroke]])
        cornerNodes.append([])
        cornerNodes[-1].append([[(maxX-minX), (maxY-minY) - stroke], [(maxX-minX), (maxY-minY)], [(maxX-minX) - stroke, (maxY-minY)]])
        cornerNodes.append([])
        cornerNodes[-1].append([[0.0 + stroke, (maxY-minY)], [0.0, (maxY-minY)], [0.0, (maxY-minY) - stroke]])
        code = []
        code.append('G21;\nG90;\nG28 X0 Y0;\nG28 Z0;\n')
        code.append('G1 Z' + formatVal(zMove + zOffset + zApproach) + ';\n')
        for nodesGroup in cornerNodes:
            maxIter = 1
            for nodes in nodesGroup:
                code += genGCode(nodes, zDraw, zMove, xOffset, yOffset, zOffset, feed, moveFeed, zMoveFeed)
        code.append('G1 Z' + formatVal(zMove + zOffset + zRetreat) + ';\n')
        code.append('G28 X0;\n')
        code.append('M84;\n;')
        f = open(fileName+'.corners.gcode', 'w')
        f.writelines(code)
        f.close()
        #Gen code for draw borders
        code = []
        code.append('G21;\nG90;\nG28 X0 Y0;\nG28 Z0;\n')
        code.append('G1 Z' + formatVal(zMove + zOffset + zApproach) + ';\n')
        for nodesGroup in [pathsNodes[0]]:
            maxIter = 1
            for nodes in nodesGroup:
                offsets = generatePathes(nodes, penRadius, maxIterations=maxIter, includeBorder=includeBorder, minPenRadius=minPenRadius)
                offsets = [offsets[0]] + offsets
                for offset in offsets:
                    try:
                        x,y = offset.xy
                        nodes = zip(x, y)
                        code += genGCode(nodes, zDraw, zMove, xOffset, yOffset, zOffset, feed, moveFeed, zMoveFeed)
                    except:
                        pass
                        #print offset
        code.append('G1 Z' + formatVal(zMove + zOffset + zRetreat) + ';\n')
        code.append('G28 X0;\n')
        code.append('M84;\n;')
        f = open(fileName+'.border.gcode', 'w')
        f.writelines(code)
        f.close()


if __name__ == "__main__":
    main(sys.argv[1:])

