from xml.dom import minidom
import numpy as np
import re
from svg.path import Path, Line, Arc, CubicBezier, QuadraticBezier, parse_path
from shapely.geometry import LineString
from shapely.geometry import LinearRing

def cmp_start_node(path1, path2):
    x1, y1 = path1.xy
    x2, y2 = path2.xy
    return x1[0] < x2[0]
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
    def correctCoordinates(self, minX, minY, mirrored):
        for ct in range(len(self.penPaths)):
            for ct2 in range(len(self.penPaths[ct])):
                self.penPaths[ct][ct2][0] -= minX
                self.penPaths[ct][ct2][1] -= minY
                if mirrored:
                    tmp = self.penPaths[ct][ct2][0]
                    self.penPaths[ct][ct2][0] = self.penPaths[ct][ct2][1]
                    self.penPaths[ct][ct2][1] = tmp

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
            for path in paths:
                descr = path.getAttribute("d")
                p = parse_path(descr)
                try:
                    length = p.length()*self.scalefactor
                except:
                    print p
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
    def process(self, mirrored):
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
    def PCBSize(self):
        return self.maxX - self.minX + 2*self.penRadius, self.maxY - self.minY + 2*self.penRadius
    def penPaths(self):
        allPaths = []
        for e in self.entryes:
            allPaths += e.penPaths
        return allPaths
        
if __name__ == "__main__":
    parcer = SVGProcessor()
    parcer.parce("Untitled-F.Cu.svg", 0.75/2)
    parcer.process(False)