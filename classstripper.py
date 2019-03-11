import getopt, sys
import glob
import os
import json

#pass ctags-Universal JSON output into this program to parse out class / structs from C++ headers (e.g. cmd>python classstripper.py typeinfo.json)
#Example cmd line:  ctags --c++-kinds=+p --fields=+ianS --extras=+q --output-format=json /pathto/yourcode/*.h > typeinfo.json

classIndex = {}
memberIndex = {}  # index of lists by class name

def main(argv):
	
	print("Loading C++ header data from " + argv[0] + " for conversion.")
	
	data_file = open(argv[0], encoding='utf-8')
	
	json_lines = data_file.readlines()
	
	#find classes
	# need to split JSON data by new lines since there is a new JSON obj on each line?
	for line in json_lines:
		data = json.loads(line)

		# add classes to their index and initialize memberIndex
		if(data["kind"] == "class" or data["kind"] == "struct" or data["kind"] == "union"):
			data["nestedclasses"] = {}  #init nested classes dict
			memberIndex[data["name"]] = []  # initialize class member index array

			if(IsNestedClass(data)):
				(scopePrefix, classname) = GetScopeParts(data["name"])
				print("Found nested class: " + classname + " belongs to: " + scopePrefix)
				classContainer = FindNestedClass(scopePrefix)
				if(classContainer is not None):
					classContainer["nestedclasses"][classname] = data

			else:
				#print("Found class to convert: " + data["name"])
				classIndex[data["name"]] = data # store classjson in class Index dict
		
		# add class members to their own index
		if(data["kind"] == "member"):
			fixedScope = FixupScope(data["scope"])
			if not fixedScope in memberIndex:
				memberIndex[fixedScope] = []
			memberIndex[fixedScope].append(data)
		
		#if we find a virtual destructor prototype, mark this class as virtual
		if(data["kind"] == "prototype" and data["pattern"].find("virtual ~") != -1):
			if(data["scope"] in classIndex): # check if class exists in index NOTE: This mainly fails for nested virtual classes, TODO Supprt nested vclasses?
				classIndex[data["scope"]]["isvirtual"] = 1
			
	
	outfileName = argv[0].replace(".json", ".h")
	print("Dumping results in " + outfileName)
	outfile = open(outfileName, "w")
	
	for cdata in classIndex.values():
		WriteClass(cdata, outfile)
		
	outfile.close()
		

#check if this json data is a nested class
def IsNestedClass(classjson):
	if(classjson["kind"] == "class" or classjson["kind"] == "struct" or classjson["kind"] == "union"):
		if(classjson["name"].find("::") != -1):
			return 1
	return 0


# Print class to file (and all nested classes!)
def WriteClass(classjson, outfile, tabPrefix = ""):

	classname = classjson["name"]
	subclass = ""

	if "inherits" in classjson:
		subclass = classjson["inherits"]

	outfile.write(tabPrefix + "// class " + classname + " inherits from " + subclass + "\n")

	writeType = "struct"
	if(classjson["kind"] == "union"):
		writeType = "union"

	(namePrefix, nameTail) = GetScopeParts(classname)

	outfile.write(tabPrefix + writeType + " " + nameTail + "\n")
	outfile.write(tabPrefix + "{\n")
		
	if(subclass != classname and subclass != ""):
		outfile.write(tabPrefix + "\t" + subclass + " m_" + subclass + " // sub class\n")
	else:
		if("isvirtual" in classjson):
			outfile.write(tabPrefix + "\tvoid** m_pVtbl; // base virtual class virtual func table pointer\n")
	
	# recursively print all nested classes
	for nestedclass in classjson["nestedclasses"].values():
		WriteClass(nestedclass, outfile, tabPrefix + "\t")

	#filter for duplicate member vars here
	membervars = {}
	for mdata in memberIndex[classname]:
		strippedVarName = StripScope(mdata["name"], classname)
		if strippedVarName != "" and not strippedVarName in membervars:
			membervars[strippedVarName] = mdata
			
	for mvars in membervars.values():
		varline = tabPrefix +  "\t" + FilterType(mvars["typeref"]) + " " + StripScope(mvars["name"], classname) + ";\n"
		outfile.write(varline)
		
	outfile.write(tabPrefix + "}; // end object " + classname + "\n\n\n")
	return

#return nested class json object (iterate down class tree of nested classes)
def FindNestedClass(classname):
	if(classname.find("::") == -1):
		if classname in classIndex:
			return classIndex[classname]
		else:
			print("FindNestedClass(" + classname + ") WARN: Could not be found in classIndex")
			return None
	else:
		scopeParts = classname.split("::")
		classout = classIndex[scopeParts[0]]
		count = 1
		while(count < len(scopeParts) and scopeParts[count] in classout["nestedclasses"]):
			classout = classout["nestedclasses"][scopeParts[count]]
			count = count + 1
		return classout


# return rest of the scope prefix (all parts of scope until last name), and scope tail ( last name after last ::)
def GetScopeParts(classname):
	if(classname.find("::") == -1):
		return (classname, classname)
	else:
		scopeprefix = ""
		scopeParts = classname.split("::")
		numScopeParts = len(scopeParts)
		# generate scope prefix
		counter = 0
		for str in scopeParts:
			scopeprefix = scopeprefix + str + "::"
			counter = counter + 1
			if counter >= numScopeParts - 1:
				break

		scopeprefix = scopeprefix[0:len(scopeprefix)-2]
		scopetail = scopeParts[len(scopeParts)-1]
		return (scopeprefix, scopetail)


# remove "typename:" prefix from ctags typename strings
def FilterType(typeref):
	return typeref.replace("typename:", "")

# remove class scope of a member var the class is already in
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