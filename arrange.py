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
    def __init__(self, x_dim, y_dim, margins, print_directions, bar):
        self.margins = margins
        self.bar = bar
        
        self.x_dim = x_dim 
        self.y_dim = y_dim
        
        self.set_margins()
        
        self.x_scan_pos = self.x_start_scan
        self.y_scan_pos = self.y_start_scan
        
        self.reflection_matrix = self.directions_to_matrix(print_directions)
        
        self.placed_objs = []

    def set_margins(self):
        self.x_start_scan = self.margins["left"]
        self.y_start_scan = self.margins["front"]
        
        self.effective_x_dim = self.x_dim - self.margins["right"]
        self.effective_y_dim = self.y_dim - self.margins["back"]

    def flip_x_y(self):
        self.margins["left"], self.margins["front"] = (self.margins["front"], self.margins["left"])
        self.margins["right"], self.margins["back"] = (self.margins["back"], self.margins["right"])
        self.x_dim, self.y_dim = (self.y_dim, self.x_dim)

    def flip_x(self):
        self.margins["left"], self.margins["right"] = (self.margins["right"], self.margins["left"])
    
    def flip_y(self):
        self.margins["front"], self.margins["back"] = (self.margins["back"], self.margins["front"])
    
    def direction_to_vec(self, direction):
        if(direction["from"] == "right"):
            return [-1, 0]
        if(direction["from"] == "left"):
            return [1, 0]
        if(direction["from"] == "front"):
            return [0, 1]
        if(direction["from"] == "back"):
            return [0, -1]
            
    def directions_to_matrix(self, print_directions):
        first_vec = self.direction_to_vec(print_directions["first"])
        second_vec = self.direction_to_vec(print_directions["second"])
        
        return [[first_vec[0], second_vec[0]],
                [first_vec[1], second_vec[1]]]
                
    def reflect_plate_according_to_print_directions(self):
        coefficients = []
        v = FreeCAD.Base.Vector(self.x_dim/float(2), self.y_dim/float(2), 0)
        w = FreeCAD.Base.Vector(-self.x_dim/float(2), -self.y_dim/float(2), 0)        

        x_transl = 0
        y_transl = 0
        
        if(self.reflection_matrix[0][0] == -1):
            self.flip_x()
        if(self.reflection_matrix[0][1] == -1):
            self.flip_y()
        if(self.reflection_matrix[1][0] == -1):
            self.flip_x()
        if(self.reflection_matrix[1][1] == -1):
            self.flip_y()

        self.set_margins()
        self.x_scan_pos = self.x_start_scan
        self.y_scan_pos = self.y_start_scan
 
        if(self.reflection_matrix[0][0] == -1):
            x_transl = self.x_dim
        if(self.reflection_matrix[0][1] == -1):
            x_transl = self.x_dim
        if(self.reflection_matrix[1][0] == -1):
            y_transl = self.y_dim
        if(self.reflection_matrix[1][1] == -1):
            y_transl = self.y_dim

        A = self.reflection_matrix
        
        transform = FreeCAD.Base.Matrix(A[0][0], A[0][1], 0, 0, 
                                        A[1][0], A[1][1], 0, 0,
                                        0,       0,       1, 0,
                                        0,       0,       0,  1
                                        )
        
        for obj in self.placed_objs:
            #reflect object according to print_direction
            bb = obj.Shape.BoundBox
            old_center = [(bb.XMax + bb.XMin) / float(2), (bb.YMax + bb.YMin) / float(2)]
            tmp_center = [A[0][0]*old_center[0] + A[0][1]*old_center[1], 
                          A[1][0]*old_center[0] + A[1][1]*old_center[1]]

            new_center = [tmp_center[0] - old_center[0] + x_transl, tmp_center[1] - old_center[1] + y_transl]
            tmp_center[0] = 0
            tmp_center[1] = 0

            if A[0][0] == 0:
                obj.Placement.Rotation = obj.Placement.Rotation.multiply(FreeCAD.Base.Rotation(FreeCAD.Base.Vector(0, 0, 1), 90))            
                bb = obj.Shape.BoundBox
                tmp_center = [(bb.XMax + bb.XMin) / float(2) - old_center[0], (bb.YMax + bb.YMin) / float(2) - old_center[1]]

            x_t = new_center[0] - tmp_center[0]
            y_t = new_center[1] - tmp_center[1]

            obj.Placement.move(FreeCAD.Vector(x_t, y_t, 0))
            
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
        y_row_spacing = extruder.extrusionPt.y_pos + safety_offset

        y_max_list_placed_objs = [placed.Shape.BoundBox.YMax for placed in self.placed_objs]
        y_max_list_placed_objs.append(0)
        y_max_placed_objs = max(y_max_list_placed_objs)

        #change x_scan_pos and y_scan_pos if needed
        # Check if object will fit on this row
        if self.x_scan_pos + x_obj_dim > self.effective_x_dim:
            # Object doesn't fit on this row, so start a new row
            self.y_scan_pos = y_max_placed_objs + y_row_spacing
            self.x_scan_pos = self.x_start_scan

        #return if obj doesn't fit on plate
        if self.y_scan_pos + y_obj_dim > self.effective_y_dim:
            return "Error: " + str(obj) + "doesn't fit on plate!"

        #place obj by translating
        x_obj = bounding_box.XMin
        y_obj = bounding_box.YMin

        x_transl = self.x_scan_pos - x_obj
        y_transl = self.y_scan_pos - y_obj
        obj.Placement.Base = FreeCAD.Vector(base.x + x_transl, base.y + y_transl, base.z)

        self.placed_objs.append(obj)

        y_max_placed_objs = max(y_max_placed_objs, obj.Shape.BoundBox.YMax)
        
        #update scan positions
        self.x_scan_pos += x_obj_dim + x_column_spacing
	    
        if(self.bar == True):
            self.y_scan_pos = max(y_max_placed_objs - (extruder.y_dim - extruder.extrusionPt.y_pos), self.y_scan_pos) #constraint coming from Printer's x-axis bar
          
        return str(obj) + " placed on plate."

def arrange_objs(objs, plate, extruder):
    placeObjsOnPlate(objs)
    plate.reflect_plate_according_to_print_directions()
    for obj in objs:
        print(obj)
        ret_str = plate.place_obj(obj, extruder)
        print(ret_str)

        #maybe return objects that couldn't be placed
        if ret_str[-1] == "!":
            plate.reflect_plate_according_to_print_directions()
            return

    plate.reflect_plate_according_to_print_directions()

def read_conf(conf_file_name):
    import json
    from pprint import pprint
    f = open(conf_file_name, 'r')
    conf_obj = json.load(f)
    pprint(conf_obj)

    plate_conf = conf_obj["plate"]
    extruder_conf = conf_obj["extruder"]
    extrusion_pt_conf = extruder_conf["extrusion_pt"]

    plate = Plate(x_dim = plate_conf["x_dim"], y_dim = plate_conf["y_dim"], margins = plate_conf["margins"], print_directions = plate_conf["print_directions"], bar = plate_conf["bar"])
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

def multi_plate_copies(objs, conf_file_name):
    '''Plates the selected objs to multiple plates inside FreeCAD.
       Sorts the objects by height to avoid collisions when changing
       rows.
    '''
    conf_path = os.path.join(confDir, conf_file_name)

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

def multi_plate_i3_berlin(objs):
    multi_plate_copies(objs, conf_file_name = 'i3berlin.json')

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
#make margins work
