from xml.dom import minidom
import numpy as np
import re
import math
from svg.path import Path, Line, Arc, CubicBezier, QuadraticBezier, parse_path
from shapely.geometry import LineString
from shapely.geometry import LinearRing
from shapely.geometry import Point
from sets import Set

def isNodesEqual(node1, node2, toleranse):
    if math.sqrt((node1[0] - node2[0])**2 + (node1[1] - node2[1])**2) < toleranse:
        return True
    return False
def oppositeEnd(end):
    if end[1] == 0:
        return (end[0], 1)
    else:
        return (end[0], 0)
def cmp_start_node(path1, path2):
    x1, y1 = path1.xy
    x2, y2 = path2.xy
    return x1[0] < x2[0]
def cmp_start_node_pad_y(pad1, pad2):
    return float(pad1.penPaths[0][0][1]) < float(pad2.penPaths[0][0][1])
def findIntersection(set1, set2, toleranse):
    minDistance = 1e10
    rez = None
    for p1 in set1:
        for p2 in set2:
            distanse = p1[0].distance(p2[0])
            if distanse < toleranse and distanse < minDistance:
                minDistance = distanse
                rez = (p1, p2, minDistance)
    return rez
def generateInfil(lineRing, penRadius, side='right', join_style=2):
    try:
        offset = lineRing.parallel_offset(penRadius, side, join_style=join_style, mitre_limit=10,resolution=16)
    except:
        return []
    parts = hasattr(offset, 'geoms') and offset or [offset]
    parts = sorted(parts, cmp=cmp_start_node)
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
            pass
    try:
        ox, oy = lineRing.xy
        if minX < min(ox) or minY < min(oy) or maxX > max(ox) or maxY > max(oy):
            # Make with 'right' side
            try:
                offset = lineRing.parallel_offset(penRadius, 'left', join_style=join_style, mitre_limit=10,resolution=16)
            except:
                pass
            parts = hasattr(offset, 'geoms') and offset or [offset]
    except:
        pass
    subparts = []
    for p in parts:
        p = p.simplify(0.05)
        if len(p.coords)  > 2:
            subparts.append(p)
            subparts += generateInfil(p, penRadius, side='right',join_style=join_style)
    return subparts
class PCBEntry(object):
    """docstring for PCBEntry"""
    def __init__(self):
        super(PCBEntry, self).__init__()
        self.penPaths = []
        self.pointCloud = []
    def process(self):
        raise NotImplemented("virtual class")
    def minMax(self):
        if len(self.penPaths) == 0:
            return 1e10, -1e10, 1e10, -1e10
        minX = []
        maxX = []
        minY = []
        maxY = []
        for p in self.penPaths:
            a = np.array(p)
            maxX.append(max(a[:,0]))
            minX.append(min(a[:,0]))
            maxY.append(max(a[:,1]))
            minY.append(min(a[:,1]))
        return min(minX), max(maxX), min(minY), max(maxY)
    def upatePointsCloud(self):
        for ctPath in range(len(self.penPaths)):
            a = np.array(self.penPaths[ctPath])
            for ctPoint in range(len(a)):
                self.pointCloud.append((Point(a[ctPoint]), ctPath, ctPoint))
    def correctCoordinates(self, minX, minY, mirrored):
        for ct in range(len(self.penPaths)):
            for ct2 in range(len(self.penPaths[ct])):
                self.penPaths[ct][ct2][0] -= minX
                self.penPaths[ct][ct2][1] -= minY
                if mirrored:
                    tmp = self.penPaths[ct][ct2][0]
                    self.penPaths[ct][ct2][0] = self.penPaths[ct][ct2][1]
                    self.penPaths[ct][ct2][1] = tmp
        self.upatePointsCloud()

class Track(PCBEntry):
    """dong for AreaToFill"""
    def __init__(self, nodes, stroke, penRadius):
        super(Track, self).__init__()
        self.nodes = np.array(nodes)
        self.nodes *= np.array([1.0, -1.0])
        self.stroke = stroke
        self.penRadius = penRadius
    def process(self):
        self.penPaths.append(self.nodes)
        line = LineString(self.nodes)
        cumBuf = self.penRadius
        buf = line
        continueFlag = True
        while continueFlag:
            if cumBuf + self.penRadius < self.stroke/2.0:
                step = self.penRadius
            else:
                step = self.stroke/2.0 - cumBuf
                continueFlag = False
                if step <= 0:
                    break
            buf = buf.buffer(step)
            cumBuf += step
            border = buf.exterior.simplify(0.05)
            x, y = border.coords.xy
            nodes = zip(x, y)
            self.penPaths.append(np.array(nodes))
    def ends(self):
        return self.penPaths[0][0], self.penPaths[0][-1]
class AreaToFill(PCBEntry):
    """docstring for AreaToFill"""
    def __init__(self, nodes, stroke, penRadius):
        super(AreaToFill, self).__init__()
        self.nodes = np.array(nodes)
        self.nodes *= np.array([1.0, -1.0])
        self.stroke = stroke
        self.penRadius = penRadius
    def process(self):
        line = LinearRing(self.nodes)
        infill = generateInfil(line, self.penRadius)
        if len(infill) == 0:
            print "failed to process infill. will try with smaller radius"
            for c in reversed(np.arange(self.penRadius*0.5, self.penRadius*0.9, self.penRadius*0.05)):
                infill = generateInfil(line, c)
                if len(infill) > 0:
                    print "Success with penRadius factor of", c/self.penRadius
                    break
        for part in infill: 
            if len(part.coords) > 0:
                x, y = part.xy
                nodes = zip(x, y)
                self.penPaths.append(np.array(nodes))
class SubPath(object):
    """doc"""
    def __init__(self):
        self.start = None
        self.stop = None
        self.path = []
        self.nextSubPaths = []
        self.collides = []
    def checkAndRegister(self, ct, objects, toleranse):
        extremsO = objects[ct].minMax()
        for track in self.path:
            extremsT = objects[track[0]].minMax()
            if extremsO[0] > extremsT[1] + toleranse:
                continue
            if extremsO[1] < extremsT[0] - toleranse:
                continue
            if extremsO[2] > extremsT[3] + toleranse:
                continue
            if extremsO[3] < extremsT[2] - toleranse:
                continue
            intersect = findIntersection(objects[track[0]].pointCloud, objects[ct].pointCloud, toleranse)
            if intersect is not None:
                self.collides.append((track[0], ct, intersect))
                return True
        for ctP in range(len(self.nextSubPaths)):
            if self.nextSubPaths[ctP].checkAndRegister(ct, objects, toleranse):
                return True
        return False
    def getPenPaths(self, tracks):
        thisPaths = np.empty([0,2])
        subPaths = np.empty([0,2])
        for t in self.path:
            thisCollides = []
            for c in self.collides:
                if c[0] == t[0]:
                    thisCollides.append(c)
            trackPaths = tracks[t[0]].penPaths
            thisCollides.sort(key=lambda c: c[2][0][2], reverse=True)
            for c in thisCollides:
                sPaths = tracks[c[1]].penPaths[0]
                for p in tracks[c[1]].penPaths[1:]:
                    sPaths = np.append(sPaths, p, axis=0)
                trackPaths[c[2][0][1]] = np.insert(trackPaths[c[2][0][1]], [c[2][0][2]], sPaths, axis=0)
            paths = trackPaths[0]
            for p in trackPaths[1:]:
                paths = np.append(paths, p, axis=0)
            trackPaths = paths
            if t[1] == 1:
                trackPaths = trackPaths[::-1]
            thisPaths = np.append(thisPaths, trackPaths, axis=0)
        for sp in self.nextSubPaths:
            subPaths = np.append(subPaths, sp.getPenPaths(tracks), axis=0)
        rez = np.append(np.append(thisPaths, subPaths, axis=0), thisPaths[::-1], axis=0)
        return rez
    def __str__(self):
        s = "start:"+str(self.start) + "\npath:" + str(self.path) + "\nstop:" + str(self.stop) + "\n"
        s += "subPaths:" + str(len(self.nextSubPaths)) + "\n"
        for sp in self.nextSubPaths:
            s += str(sp)
        return s
def generateSubPath(pathID, start):
    global connectedTracks
    global tracksConnectDict
    p = SubPath()
    p.start = start
    last = p.start
    while len(connectedTracks[pathID]) > 0:
        p.path.append(last)
        connectedTracks[pathID].remove(last[0])
        connectedTo = tracksConnectDict.get(oppositeEnd(last), [])
        if len(connectedTo) == 1:
            last = connectedTo[0]
        elif len(connectedTo) > 1:
            p.stop = oppositeEnd(last)
            for c in connectedTo:
                p.nextSubPaths.append(generateSubPath(pathID, c))
            return p
        elif len(connectedTo) == 0:
            p.stop = oppositeEnd(last)
            return p
        else:
            raise NotImplemented
class SVGProcessor(object):
    """docstring for SVGProcessor"""
    def __init__(self):
        super(SVGProcessor, self).__init__()
        self.width = None
        self.height = None
        self.bound = None
        self.translate = [0.0, 0.0]
        self.scale = [1.0, 1.0]
        self.scalefactor = 1.0
        self.entryes = []
    def parce(self, fileName, penRadius):
        self.penRadius = penRadius
        doc = minidom.parse(fileName)
        svg = doc.getElementsByTagName("svg")[0]
        r = re.compile("^([0-9]*\.?[0-9]*)(cm|mm)$")
        s = r.search(svg.getAttribute("width"))
        self.width = float(s.group(1))
        if s.group(2) == "cm":
            self.width *= 10;
        s = r.search(svg.getAttribute("height"))
        self.height = float(s.group(1))
        if s.group(2) == "cm":
            self.height *= 10;
        r = re.compile("^([-+]?[0-9]*\.?[0-9]*)\s([-+]?[0-9]*\.?[0-9]*)\s([-+]?[0-9]*\.?[0-9]*)\s([-+]?[0-9]*\.?[0-9]*)\s?$")
        s = r.search(svg.getAttribute("viewBox"))
        self.bound = [float(s.group(1)), float(s.group(2)), float(s.group(3)), float(s.group(4))]
        self.scalefactor = (self.width/(self.bound[2] - self.bound[0]) + self.height/(self.bound[3] - self.bound[1]))/2.0
        groups = svg.getElementsByTagName("g")
        rTS = re.compile("^translate\(([-+]?[0-9]*\.?[0-9]*)\s([-+]?[0-9]*\.?[0-9]*)\)\sscale\(([-+]?[0-9]*\.?[0-9]*)\s([-+]?[0-9]*\.?[0-9]*)\)$")
        for g in groups:
            try:
                sTS = rTS.search(g.getAttribute("transform"))
                self.translate = [float(sTS.group(1)), float(sTS.group(2))]
                self.scale = [float(sTS.group(1)), float(sTS.group(2))]
            except:
                pass
            style = g.getAttribute("style")
            rFill = re.compile("fill-opacity:([0-9]*\.?[0-9]*);")
            sFill = rFill.search(style)
            rStroke = re.compile("stroke-opacity:([0-9]*\.?[0-9]*);")
            sStroke = rStroke.search(style)
            rSWidth = re.compile("stroke-width:([0-9]*\.?[0-9]*);")
            sSWidth = rSWidth.search(style)
            try:
                fill = float(sFill.group(1))
            except:
                fill = 0.0
            try:
                stroke = float(sStroke.group(1))
            except:
                stroke = 0.0
            try:
                sWidth = round(float(sSWidth.group(1))*self.scalefactor, 2)
            except:
                sWidth = 0.0
            paths = g.getElementsByTagName("path")
            polylines = g.getElementsByTagName("polyline")
            circles = g.getElementsByTagName("circle")
            for path in paths:
                descr = path.getAttribute("d")
                p = parse_path(descr)
                try:
                    length = p.length()*self.scalefactor
                except:
                    point = p.point(0)*self.scalefactor
                    cx, cy = round(point.real, 2), round(point.imag, 2)
                    nodes = []
                    for fi in np.arange(0, 2*math.pi, math.pi/30):
                        nodes.append([cx + (sWidth/2)*math.cos(fi), cy + (sWidth/2)*math.sin(fi)])
                    self.entryes.append(AreaToFill(nodes, sWidth, penRadius))
                    continue
                numCheckPoints = length*3/penRadius
                points = []
                cs = [0.0]
                for c in np.arange(1.0/numCheckPoints, 0.999, 1.0/numCheckPoints):
                    cs.append(c)
                cs.append(1.0)
                for c in cs:
                    point = p.point(c)*self.scalefactor
                    points.append([round(point.real, 2), round(point.imag, 2)])
                self.entryes.append(Track(points, sWidth, penRadius))
            for polyline in polylines:
                points = polyline.getAttribute("points")
                nodes = []
                for pair in points.split(" "):
                    p = pair.split(",")
                    if len(p) == 2:
                        nodes.append([round(float(p[0])*self.scalefactor, 1), round(float(p[1])*self.scalefactor, 1)])
                self.entryes.append(AreaToFill(nodes, sWidth, penRadius))
            for circle in circles:
                cx = round(float(circle.getAttribute("cx"))*self.scalefactor, 1)
                cy = round(float(circle.getAttribute("cy"))*self.scalefactor, 1)
                r  = round(float(circle.getAttribute("r") )*self.scalefactor, 1)
                nodes = []
                for fi in np.arange(0, 2*math.pi, math.pi/30):
                    nodes.append([cx + (r+sWidth)*math.cos(fi), cy + (r+sWidth)*math.sin(fi)])
                if fill == 1:
                    self.entryes.append(AreaToFill(nodes, sWidth, penRadius))
                else:
                    self.entryes.append(Track(nodes, sWidth, penRadius))
    def process(self, mirrored):
        global connectedTracks
        global tracksConnectDict
        minX = []
        maxX = []
        minY = []
        maxY = []
        for e in self.entryes:
            e.process()
            lMinX, lMaxX, lMinY, lMaxY = e.minMax()
            minX.append(lMinX)
            maxX.append(lMaxX)
            minY.append(lMinY)
            maxY.append(lMaxY)
        self.minX = min(minX)
        self.maxX = max(maxX)
        self.minY = min(minY)
        self.maxY = max(maxY)
        for e in self.entryes:
            e.correctCoordinates(self.minX, self.minY, mirrored)
        if mirrored:
            tmp = self.minX
            self.minX = self.minY
            self.minY = tmp
            tmp = self.maxX
            self.maxX = self.maxY
            self.maxY = tmp
        tracks = []
        pads = []
        for e in self.entryes:
            if isinstance(e, Track):
                tracks.append(e)
            elif isinstance(e, AreaToFill):
                pads.append(e)
            else:
                raise NotImplemented

        #Merge connected tracks
        tracksConnectivity = []
        tracksConnectDict = dict()
        for ct1 in range(len(tracks)-1):
            ends1 = tracks[ct1].ends()
            for ct2 in range(ct1+1, len(tracks)):
                ends2 = tracks[ct2].ends()
                if isNodesEqual(ends1[0], ends2[0], self.penRadius/2):
                    tracksConnectivity.append((ct1, ct2, 0, 0))
                    tracksConnectDict[(ct1, 0)] = tracksConnectDict.get((ct1, 0), []) + [(ct2, 0)]
                    tracksConnectDict[(ct2, 0)] = tracksConnectDict.get((ct2, 0), []) + [(ct1, 0)]
                elif isNodesEqual(ends1[0], ends2[1], self.penRadius/2):
                    tracksConnectivity.append((ct1, ct2, 0, 1))
                    tracksConnectDict[(ct1, 0)] = tracksConnectDict.get((ct1, 0), []) + [(ct2, 1)]
                    tracksConnectDict[(ct2, 1)] = tracksConnectDict.get((ct2, 1), []) + [(ct1, 0)]
                elif isNodesEqual(ends1[1], ends2[0], self.penRadius/2):
                    tracksConnectivity.append((ct1, ct2, 1, 0))
                    tracksConnectDict[(ct1, 1)] = tracksConnectDict.get((ct1, 1), []) + [(ct2, 0)]
                    tracksConnectDict[(ct2, 0)] = tracksConnectDict.get((ct2, 0), []) + [(ct1, 1)]
                elif isNodesEqual(ends1[1], ends2[1], self.penRadius/2):
                    tracksConnectivity.append((ct1, ct2, 1, 1))
                    tracksConnectDict[(ct1, 1)] = tracksConnectDict.get((ct1, 1), []) + [(ct2, 1)]
                    tracksConnectDict[(ct2, 1)] = tracksConnectDict.get((ct2, 1), []) + [(ct1, 1)]
        connectedTracks = []
        for conn in tracksConnectivity:
            connectedTracks.append(Set([conn[0], conn[1]]))
        modified = True
        while modified:
            modified = False
            for ct1 in range(len(connectedTracks)-1):
                for ct2 in range(ct1+1, len(connectedTracks)):
                    if len(connectedTracks[ct1] & connectedTracks[ct2]) > 0:
                        connectedTracks[ct1] = connectedTracks[ct1] | connectedTracks[ct2]
                        modified = True
                        connectedTracks.pop(ct2)
                        break
                if modified:
                    break
        endsMap = []
        for seq in connectedTracks:
            endsMap.append(dict())
            for s in seq:
                for conn in tracksConnectivity:
                    if conn[0] == s:
                        endsMap[-1][(conn[0], conn[2])] = endsMap[-1].get((conn[0], conn[2]), 0) + 1
                    if conn[1] == s:
                        endsMap[-1][(conn[1], conn[3])] = endsMap[-1].get((conn[1], conn[3]), 0) + 1
        freeEnds = []
        for seq in connectedTracks:
            freeEnds.append([])
            for s in seq:
                freeEnds[-1].append((s, 0))
                freeEnds[-1].append((s, 1))
        for conn in tracksConnectivity:
            for ct in range(len(freeEnds)):
                if freeEnds[ct].count((conn[0], conn[2])):
                    freeEnds[ct].remove((conn[0], conn[2]))
                if freeEnds[ct].count((conn[1], conn[3])):
                    freeEnds[ct].remove((conn[1], conn[3]))
        self.allPaths = []
        for pathID in range(len(connectedTracks)):
            end = freeEnds[pathID][0]
            p = generateSubPath(pathID, end)
            self.allPaths.append(p)
        
        #Merge hanging tracks and pads
        
        #.... Mmmm...
        tracks +=pads
        hangingObjectsIDs = []
        for ct in range(len(tracks)):
            if (not tracksConnectDict.has_key((ct, 0))) and (not tracksConnectDict.has_key((ct, 1))):
                hangingObjectsIDs.append(ct)

        stillHangingObjectsIDs = []
        for ct in hangingObjectsIDs:
            found = False
            for sp in self.allPaths:
                if sp.checkAndRegister(ct, tracks, self.penRadius*2):
                    found = True
                    break
            if not found:
                stillHangingObjectsIDs.append(ct)
        self.tracks = tracks
        for sho in stillHangingObjectsIDs:
            p=SubPath()
            p.start=(sho, 0)
            p.path.append(p.start)
            p.stop=oppositeEnd(p.start)
            self.allPaths.append(p)
        
    def PCBSize(self):
        return self.maxX - self.minX + 2*self.penRadius, self.maxY - self.minY + 2*self.penRadius
    def penPaths(self):
        allPaths = []
        for sp in self.allPaths:
            allPaths.append(sp.getPenPaths(self.tracks))
        return allPaths
        
if __name__ == "__main__":
    parcer = SVGProcessor()
    parcer.parce("Untitled-F.Cu.svg", 0.75/2)
    parcer.process(False)