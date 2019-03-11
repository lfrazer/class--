import getopt, sys
import glob
import os
import json

#pass ctags-Universal JSON output into this program to parse out class / structs from C++ headers

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
			if not data["scope"] in memberIndex:
				memberIndex[data["scope"]] = []
			memberIndex[data["scope"]].append(data)
			
	
	outfileName = argv[0].replace(".json", ".h")
	outfile = open(outfileName, "w")
	
	for cdata in classIndex.values():
		classname = cdata["name"]
		outfile.write("struct " + classname + "\n{\n")
		
		#filter for duplicate member vars here
		membervars = {}
		for mdata in memberIndex[classname]:
			strippedVarName = StripScope(mdata["name"], classname)
			if not strippedVarName in membervars:
				membervars[strippedVarName] = mdata
			
		for mvars in membervars.values():
			varline = "\t" + FilterType(mvars["typeref"]) + " " + StripScope(mvars["name"], classname) + ";\n"
			outfile.write(varline)
		
		outfile.write("}; // end object " + cdata["name"] + "\n\n\n")
		
	outfile.close()
		
		
	
def FilterType(typeref):
	return typeref.replace("typename:", "")

def StripScope(varname, className):
	varname = varname.replace(className + "::", "")
	return varname
	
if __name__ == "__main__":
   main(sys.argv[1:])