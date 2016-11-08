import FreeCAD

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
    def __init__(self, x_dim, y_dim):
        self.x_dim = x_dim
        self.y_dim = y_dim
        self.x_scan_pos = 0
        self.y_scan_pos = 0
        self.placed_objs = []

    def __repr__(self):
        return "(Plate) {" + "width: " + str(self.x_dim) + ", depth: " + str(self.y_dim) + "}"

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
        x_scan_pos_next = self.x_scan_pos + x_column_spacing + x_obj_dim
        if x_scan_pos_next > self.x_dim:
            self.x_scan_pos = 0
            x_scan_pos_next = self.x_scan_pos + x_column_spacing + x_obj_dim
            self.y_scan_pos = y_max_placed_objs + y_row_spacing

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
        self.x_scan_pos = x_scan_pos_next
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

    plate = Plate(x_dim = plate_conf["x_dim"], y_dim = plate_conf["y_dim"])
    extruder = Extruder(x_dim = extruder_conf["x_dim"], y_dim = extruder_conf["y_dim"], x_pos = extrusion_pt_conf["x_pos"], y_pos = extrusion_pt_conf["y_pos"])
    return (plate, extruder)


doc = FreeCAD.ActiveDocument
objs = doc.Objects

def printObjsBase(objs):
  for obj in objs:
	print(obj.Placement.Base)

def printObjsBoundingBox(objs):
    for obj in objs:
        print(obj.Shape.BoundBox)

printObjsBase(objs)
confDir = os.path.dirname(os.path.realpath(__file__))
plate, extruder = read_conf(os.path.join(confDir, "arrangeCnf.json"))

#TODO
#Exception Handling
#Clear Objs
#do testing (e.g. for connectors)
