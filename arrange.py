import FreeCAD, FreeCADGui, Draft
import os
import copy

def placeObjsOnPlate(objs):
    for obj in objs:
        base = obj.Placement.Base
        boundingBox = obj.Shape.BoundBox
        lowerEnd = boundingBox.ZMin
        obj.Placement.Base = FreeCAD.Vector(base[0], base[1], base[2] - lowerEnd)

class Extruder:
    class ExtrusionPoint:
        def __init__(self, x_pos, y_pos):
            self.x_pos = x_pos
            self.y_pos = y_pos

        def __repr__(self):
            return "(Extrusion Point) {" + "xPosition: " + str(self.x_pos) + ", yPosition: " + str(self.y_pos) + "}"

    def __init__(self, x_dim, y_dim, x_pos, y_pos):
        self.x_dim = x_dim
        self.y_dim = y_dim
        self.extrusionPt = self.ExtrusionPoint(x_pos, y_pos)

    def __repr__(self):
        return "(Extruder) {"  + "width: " + str(self.x_dim) + ", depth: " + str(self.y_dim) + ", " + str(self.extrusionPt) + "}"




class Plate:
    def __init__(self, x_dim, y_dim, margins):
        self.margins = margins
        self.x_dim = x_dim - self.margins["right"]
        self.y_dim = y_dim - self.margins["back"]
        self.x_scan_pos = margins["left"]
        self.y_scan_pos = margins["front"]
        self.placed_objs = []

    def __repr__(self):
        return "(Plate) {" + "width: " + str(self.x_dim) + ", depth: " + str(self.y_dim) + "}"

    def viz(self):
        Draft.makeRectangle(self.x_dim, self.y_dim)
        
    def place_obj(self, obj, extruder):
        #get relevant information from obj
        bounding_box = obj.Shape.BoundBox
        x_obj_dim = bounding_box.XLength
        y_obj_dim = bounding_box.YLength
        base      = obj.Placement.Base

        #determine offsets
        safety_offset = 5
        x_column_spacing = extruder.extrusionPt.x_pos + safety_offset
        y_row_spacing    = extruder.extrusionPt.y_pos + safety_offset

        y_bound_placed_objs = [placed.Shape.BoundBox.YMax for placed in self.placed_objs]
        y_bound_placed_objs.append(0)
        y_max_placed_objs = max(y_bound_placed_objs)

        #change x_scan_pos and y_scan_pos if needed
        # Check if object will fit on this row
        if self.x_scan_pos + x_obj_dim > self.x_dim:
            # Object doesn't fit on this row, so start a new row
            self.y_scan_pos = y_max_placed_objs + y_row_spacing
            self.x_scan_pos = self.margins["left"]

        #return if obj doesn't fit on plate
        if self.y_scan_pos + y_obj_dim > self.y_dim:
            return "Error: " + str(obj) + "doesn't fit on plate!"

        #place obj by translating
        x_min_obj = bounding_box.XMin
        y_min_obj = bounding_box.YMin
        x_transl = self.x_scan_pos - x_min_obj
        y_transl = self.y_scan_pos - y_min_obj
        obj.Placement.Base = FreeCAD.Vector(base.x + x_transl, base.y + y_transl, base.z)

        self.placed_objs.append(obj)

        y_max_placed_objs = max(y_max_placed_objs, obj.Shape.BoundBox.YMax)
        #update scan positions
        self.x_scan_pos += x_obj_dim + x_column_spacing
        self.y_scan_pos = max(y_max_placed_objs - (extruder.y_dim - extruder.extrusionPt.y_pos), self.y_scan_pos) #constraint coming from Printer's x-axis bar

        return str(obj) + " placed on plate."

def arrange_objs(objs, plate, extruder):
    for obj in objs:
        print(obj)
        ret_str = plate.place_obj(obj, extruder)
        print(ret_str)

        #maybe return objects that couldn't be placed
        if ret_str[-1] == "!":
            return

def read_conf(conf_file_name):
    import json
    from pprint import pprint
    f = open(conf_file_name, 'r')
    conf_obj = json.load(f)
    pprint(conf_obj)

    plate_conf = conf_obj["plate"]
    extruder_conf = conf_obj["extruder"]
    extrusion_pt_conf = extruder_conf["extrusion_pt"]

    plate = Plate(x_dim = plate_conf["x_dim"], y_dim = plate_conf["y_dim"], margins = plate_conf["margins"])
    extruder = Extruder(x_dim = extruder_conf["x_dim"], y_dim = extruder_conf["y_dim"], x_pos = extrusion_pt_conf["x_pos"], y_pos = extrusion_pt_conf["y_pos"])
    return (plate, extruder)

def plate_objs(objs, plate, extruder, prefix=None):
    '''Place the objs on a plate.
       If the prefix is given, it's added to the object labels, e.g. "V1","V2" becomes "P1 V1", "P1 V2"
    '''
    arrange_objs(objs, plate, extruder)
    placeObjsOnPlate(plate.placed_objs)
    if prefix:
        index = 1
        for obj in plate.placed_objs:
            if not obj.Label.startswith(prefix):
                obj.Label = "%s-%d %s" % (prefix, index, obj.Label)
            index += 1
    if len(objs) != len(plate.placed_objs):
        print "Warning: %d objects were not placed" % (len(objs) - len(plate.placed_objs))

def multi_plate_objs(objs, conf_file_name):
    '''Place objects on multiple plates. Returns array of plates containing placed objects.'''
    plates = []
    to_place = copy.copy(objs)

    while len(to_place) > 0:
        plate, extruder = read_conf(conf_file_name)
        plate_number = len(plates) + 1
        plate_objs(to_place, plate, extruder, prefix = "P%d" % plate_number)

        if not plate.placed_objs:
            print "Error: Couldn't place any object on plate"
            break

        plates.append(plate)

        for obj in plate.placed_objs:
            to_place.remove(obj)

    if len(to_place) != 0:
        print "Warning: %d objects were NOT placed" % len(to_place)

    return plates

# FreeCAD-specific helper functions
def sorted_by_height(objs, ascending=True):
    '''Returns new list of FreeCAD objects sorted by bounding box height'''
    return sorted(objs, key=z_length_key, reverse=not ascending)

def z_length_key(obj):
    '''Returns object height from bounding box'''
    return obj.Shape.BoundBox.ZLength

def make_simple_copy(obj, postfix=None):
    '''Create a simple (non-parametric) copy of the object and return it'''
    if postfix:
        newLabel = obj.Label + postfix
    else:
        newLabel = obj.Label

    newObj = obj.Document.addObject("Part::Feature", newLabel)
    newObj.Shape = obj.Shape
    newObj.Label = newLabel
    return newObj

def multi_plate_i3_berlin(objs):
    '''Plates the selected objs to multiple plates inside FreeCAD'''
    conf_path = os.path.join(confDir, 'i3berlin.json')

    copy_postfix = 'p'

    by_height = sorted_by_height(objs) # make sure the extruder is above existing objects when changing rows
    to_place = []
    for obj in by_height:
        to_place.append(make_simple_copy(obj, postfix=copy_postfix))
    multi_plate_objs(to_place, conf_path)

    # postfix is no longer necessary
    for obj in to_place:
        if obj.Label.endswith(copy_postfix):
            obj.Label = obj.Label[:-1]

    to_place[0].Document.recompute()

def getActiveDoc():
    return FreeCAD.ActiveDocument

def getSelectedObjs():
    return FreeCADGui.Selection.getSelection()

def printObjsBase(objs):
  for obj in objs:
	print(obj.Placement.Base)

def printObjsBoundingBox(objs):
    for obj in objs:
        print(obj.Shape.BoundBox)

#printObjsBase(objs)
confDir = os.path.dirname(os.path.realpath(__file__))
confFilePath = os.path.join(confDir, "arrangeCnf.json")
plate, extruder = read_conf(confFilePath)

#TODO
#Exception Handling
#Clear Objs
#do testing (e.g. for connectors)
