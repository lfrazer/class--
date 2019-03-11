import getopt, sys
import glob
import os
import json

#pass ctags-Universal JSON output into this program to parse out class / structs from C++ headers (e.g. cmd>python classstripper.py typeinfo.json)
#Example cmd line:  ctags --c++-kinds=+p --fields=+ianS --extras=+q --output-format=json /pathto/yourcode/*.h > typeinfo.json

def main(argv):
	data_file = open(argv[0], encoding='utf-8')
	#data = json.loads(data_file.read())
	
	json_lines = data_file.readlines()
	
	classIndex = {}
	memberIndex = {}  # index of lists by class name
	
	#find classes
	# need to split JSON data by new lines since there is a new JSON obj on each line?
	for line in json_lines:
		data = json.loads(line)
		if((data["kind"] == "class" or data["kind"] == "struct")):
			print("Found class to convert: " + data["name"])
			classIndex[data["name"]] = data
			memberIndex[data["name"]] = []
		
		if(data["kind"] == "member"):
			fixedScope = FixupScope(data["scope"])
			if not fixedScope in memberIndex:
				memberIndex[fixedScope] = []
			memberIndex[fixedScope].append(data)
		
		#if we find a virtual destructor prototype, mark this class as virtual
		if(data["kind"] == "prototype" and data["pattern"].find("virtual ~") != -1):
			classIndex[data["scope"]]["isvirtual"] = 1
			
	
	outfileName = argv[0].replace(".json", ".h")
	outfile = open(outfileName, "w")
	
	for cdata in classIndex.values():
		classname = cdata["name"]
		subclass = ""

		if "inherits" in cdata:
			subclass = cdata["inherits"]

		outfile.write("// class " + classname + " inherits from " + subclass + "\n")
		outfile.write("struct " + classname + "\n{\n")
		
		if(subclass != classname and subclass != ""):
			outfile.write("\t" + subclass + " m_" + subclass + " // sub class\n")
		else:
			if("isvirtual" in cdata):
				outfile.write("\tvoid** m_pVtbl; // base virtual class virtual func table pointer\n")
		#filter for duplicate member vars here
		membervars = {}
		for mdata in memberIndex[classname]:
			strippedVarName = StripScope(mdata["name"], classname)
			if strippedVarName != "" and not strippedVarName in membervars:
				membervars[strippedVarName] = mdata
			
		for mvars in membervars.values():
			varline = "\t" + FilterType(mvars["typeref"]) + " " + StripScope(mvars["name"], classname) + ";\n"
			outfile.write(varline)
		
		outfile.write("}; // end object " + cdata["name"] + "\n\n\n")
		
	outfile.close()
		
		
	
def FilterType(typeref):
	return typeref.replace("typename:", "")

def StripScope(varname, className):
	if(varname.find("__anon") != -1):
		return ""  #ignore anon scope variables
	varname = varname.replace(className + "::", "")
	return varname

# removes anonymous scope
def FixupScope(scope):
    if(scope.find("::") == -1):
        return scope
    scopeout = ""
    scopeParts = scope.split("::")
    numScopeParts = len(scopeParts)
    if scopeParts[len(scopeParts)-1].find("__anon") != -1:
        numScopeParts = numScopeParts - 1

    counter = 0
    for str in scopeParts:
        scopeout = scopeout + str + "::"
        counter = counter + 1
        if counter >= numScopeParts:
            break

    scopeout = scopeout[0:len(scopeout)-2]
    return scopeout

if __name__ == "__main__":
   main(sys.argv[1:])