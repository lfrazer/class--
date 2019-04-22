# class-- (class stripper) by lfrazer
# lfrazer/class-- is licensed under the
#GNU General Public License v3.0
# See LICENSE file for details
# Convert C++ classes to C structures

import getopt, sys
import os
import json
import re

#pass ctags-Universal JSON output into this program to parse out class / structs from C++ headers (e.g. cmd>python classstripper.py typeinfo.json)
#Important note:  Tell ctags not to sort to keep member variables in correct order
#Example cmd line:  ctags --c++-kinds=+p --fields=+ianS --extras=+q --sort=no --output-format=json /pathto/yourcode/*.h > typeinfo.json


class CClassStripper:
	def __init__(self):
		self.nativeTypes = ["T", "void", "int", "char", "const char", "wchar_t", "const wchar_t", "long", "float", "double", "unsigned", "unsigned int", "unsigned long", "long long", "unsigned long long", "int8_t", "int16_t", "int32_t", "int64_t", "uint8_t", "uint16_t", "uint32_t", "uint64_t", "SInt8", "SInt16", "SInt32", "SInt64", "UInt8", "UInt16", "UInt32", "UInt64", "Float32", "Float64"]
		self.classIndex = {}
		self.memberIndex = {}  # index of lists by class name
		self.forwardDeclrations = {}  # print forward declarations for non-native ptr types
		self.enumIndex = {}
		self.enumConstantIndex = {}


	#check if this json data is a nested class
	def IsNestedClass(self, classjson):
		if(classjson["kind"] == "class" or classjson["kind"] == "struct" or classjson["kind"] == "union"):
			if(classjson["name"].find("::") != -1):
				return 1
		return 0

	def Process(self, filepath):
		print("Loading C++ header data from " + filepath + " for conversion.")
	
		data_file = open(filepath, encoding='utf-8')
	
		json_lines = data_file.readlines()
	
		#find classes
		# need to split JSON data by new lines since there is a new JSON obj on each line?
		for line in json_lines:
			data = json.loads(line)

			# add classes to their index and initialize memberIndex
			if(data["kind"] == "class" or data["kind"] == "struct" or data["kind"] == "union"):
				data["nestedclasses"] = {}  #init nested classes dict
				self.memberIndex[data["name"]] = []  # initialize class member index array

				if(self.IsNestedClass(data)):
					(scopePrefix, classname) = self.GetScopeParts(data["name"])
					#print("Found nested class: " + classname + " belongs to: " + scopePrefix)
					classContainer = self.FindNestedClass(scopePrefix)
					if(classContainer is not None):
						classContainer["nestedclasses"][classname] = data

				elif(not "scope" in data):  # check if this is really not a nested class
					#print("Found class to convert: " + data["name"])
					self.classIndex[data["name"]] = data # store classjson in class Index dict
		
			# add class members to their own index
			elif(data["kind"] == "member"):
				fixedScope = data["scope"] # no longer need to fixupscope due to handling nested classes/unions
				if not fixedScope in self.memberIndex:
					self.memberIndex[fixedScope] = []

				# don't store member if it is static (C structs have no static members and not relevant to offsets anyway)
				if(re.search(r'static\s+', data["pattern"]) is None):
					self.memberIndex[fixedScope].append(data)
				#else:
				#	print("Skipping static member: " + data["pattern"] + "\n")

				# store ptr types in forward declaration if needed
				cleanedType = self.FilterTemplate(self.FilterType(data["typeref"]))
				if cleanedType.find("*") != -1 and re.search(r'\(\*.*\)', cleanedType) is None:  #however, avoid creating forward decl for function pointers
					cleanedType = cleanedType.replace("*", "")
					cleanedType = re.sub("\[.*\]", "", cleanedType)
					cleanedType = cleanedType.strip()
					if(cleanedType not in self.nativeTypes and cleanedType not in self.forwardDeclrations):
						self.forwardDeclrations[cleanedType] = 1
					
		
			#if we find a virtual function of any kind, mark this class as virtual
			elif(data["kind"] == "prototype" or data["kind"] == "function"):
				if(re.search(r'virtual\s+.*\(', data["pattern"]) is not None):   # regex match virtual destructor functions  
					if(data["scope"] in self.classIndex): # check if class exists in index NOTE: This mainly fails for nested virtual classes, TODO Supprt nested vclasses?
						self.classIndex[data["scope"]]["isvirtual"] = 1

			# handle enum and enum constants
			# this works a little differently from classes, we don't want any nested stuff since IDA will change the  struct offset if there is nested enum typedefs - so we want to extract all of them from classes
			elif(data["kind"] == "enum"):
				enumName = data["name"].replace("::", "__")
				self.enumIndex[enumName] = data

			elif(data["kind"] == "enumerator"):
				enumScope = data["scope"].replace("::", "__")
				if not enumScope in self.enumConstantIndex:
					self.enumConstantIndex[enumScope] = []
				self.enumConstantIndex[enumScope].append(data)

			
	
		outfileName = filepath.replace(".json", ".h")
		print("Dumping results in " + outfileName)
		outfile = open(outfileName, "w")

		outfile.write("// Forward Declarations \n\n")

		#write forward declarations
		for decl in self.forwardDeclrations.keys():
			outfile.write("struct " + decl + ";\n")


		outfile.write("\n\n// Enums \n\n") 
		#write enums
		for enumjson in self.enumIndex.values():
			self.WriteEnum(enumjson, outfile)

		outfile.write("\n\n// Structures \n\n")

		# Write all structures
		for cdata in self.classIndex.values():
			self.WriteClass(cdata, outfile)
		
		outfile.close()
		

	# Print enum and all constant members
	def WriteEnum(self, enumjson, outfile):
		enumName = enumjson["name"].replace("::", "__")

		#skip if this enum has no actual constant values in it
		if(enumName not in self.enumConstantIndex):
			return

		#filter for duplicate enum constant vals here
		constvals = {}
		for cdata in self.enumConstantIndex[enumName]:
			(scopehead, fixedVarName) = self.GetScopeParts(cdata["name"])
			if fixedVarName != "" and not fixedVarName in constvals:
				constvals[fixedVarName] = cdata

		outfile.write("enum " + enumName + " \n")
		outfile.write("{\n")
		for enumConstant in constvals.values():
			fixedPattern = self.FixupPattern(enumConstant["pattern"])
			#clean pattern further for case of one-liner enum  which will double up enum definition wrongly
			fixedPattern = re.sub("enum\s+\{", "", fixedPattern)
			fixedPattern = re.sub("\}\s*;", "", fixedPattern)
			outfile.write("\t" + fixedPattern + "\n")
		outfile.write("};\n\n")


	# Print class to file (and all nested classes!)
	def WriteClass(self, classjson, outfile, tabPrefix = ""):

		classname = classjson["name"]
		subclass = ""

		if "inherits" in classjson:
			subclass = classjson["inherits"]
			outfile.write(tabPrefix + "// class " + classname + " inherits from " + subclass + "\n")
		else:
			outfile.write(tabPrefix + "// class " + classname + " is a base class.\n")

		writeType = "struct"
		if(classjson["kind"] == "union"):
			writeType = "union"

		(namePrefix, nameTail) = self.GetScopeParts(classname)

		outfile.write(tabPrefix + writeType + " " + self.FilterTemplate(nameTail) + "\n")
		outfile.write(tabPrefix + "{\n")
		
		if(subclass != classname and subclass != ""):
			subclass = self.FilterTemplate(subclass)
			# Try to support multiple inheritance
			if(subclass.find(",") != -1):
				subclassList = subclass.split(",")
				for sclass in subclassList:
					outfile.write(tabPrefix + "\t" + sclass + " m_" + sclass + "; // sub class (Multiple-inheritance)\n")
			else:
				outfile.write(tabPrefix + "\t" + subclass + " m_" + subclass + "; // sub class\n")

		else:
			if("isvirtual" in classjson):
				outfile.write(tabPrefix + "\tvoid** m_pVtbl; // base virtual class virtual func table pointer\n")
	
		# recursively print all nested classes
		for nestedclass in classjson["nestedclasses"].values():
			self.WriteClass(nestedclass, outfile, tabPrefix + "\t")

		#filter for duplicate member vars here
		membervars = {}
		for mdata in self.memberIndex[classname]:
			strippedVarName = self.StripScope(mdata["name"], classname)
			if strippedVarName != "" and not strippedVarName in membervars:
				membervars[strippedVarName] = mdata
			
		for mvars in membervars.values():
			varline = ""
			fixedPattern = self.FixupPattern(mvars["pattern"])
			commaPos = fixedPattern.find(",")
			commentPos = fixedPattern.find("//")
			if( (commaPos == -1 or commaPos >= commentPos) and fixedPattern.find("<ErrorType>") == -1):  # NOTE: printing the pattern goes horribly wrong when the struct declares multiple vars on one line with commas, if this is the case we need to fallback to old way of printing
				varline = tabPrefix + "\t" + self.FilterTemplate(fixedPattern) + "\n" # Write vars with pattern to preserve array sizes and comments
			else:
				(scopePrefix, typeName) = self.GetScopeParts(self.FilterType(mvars["typeref"]))
				varline = tabPrefix +  "\t" + self.FilterTemplate(typeName)  + " " +  self.FilterTemplate(mvars["name"]) + "; // Generated var type due to FixupPattern() issue\n"

			outfile.write(varline)
		
		outfile.write(tabPrefix + "}; // end object " + classname + "\n\n\n")
		return

	#return nested class json object (iterate down class tree of nested classes)
	def FindNestedClass(self, classname):
		if(classname.find("::") == -1):
			if classname in self.classIndex:
				return self.classIndex[classname]
			else:
				print("FindNestedClass(" + classname + ") WARN: Could not be found in classIndex")
				return None
		else:
			scopeParts = classname.split("::")
			classout = self.classIndex[scopeParts[0]]
			count = 1
			while(count < len(scopeParts) and scopeParts[count] in classout["nestedclasses"]):
				classout = classout["nestedclasses"][scopeParts[count]]
				count = count + 1
			return classout


	# return rest of the scope prefix (all parts of scope until last name), and scope tail ( last name after last ::)
	def GetScopeParts(self, classname):
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


	# remove template parameters inside < ... >
	def FilterTemplate(self, name):
		return re.sub("<.*>", "", name)

	# remove "typename:" prefix from ctags typename strings
	def FilterType(self, typeref):
		return typeref.replace("typename:", "")

	# Fix up pattern - remove junk text and fix comments
	def FixupPattern(self, pattern):
		if len(pattern) > 4:
			pattern = pattern[2:len(pattern)-2]
			pattern = pattern.replace("\\/\\/", "//")
			pattern = pattern.replace("\\/*", "/*")
			pattern = pattern.replace("*\\/", "*/")
			if(pattern.strip()[0] == "}"):  # special case, trailing struct/union name 
				pattern = "// <ErrorType> " + pattern  # Sometimes Ctags JSON data gives us bad types from the trailing brace of a C-style structure with name (typedef style?), handle this case
		return pattern

	# remove class scope of a member var the class is already in
	def StripScope(self, varname, className):
		#if(varname.find("__anon") != -1):
		#	return ""  #ignore anon scope variables
		varname = varname.replace(className + "::", "")
		return varname

	# removes anonymous scope
	def FixupScope(self, scope):
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
	if(len(sys.argv) < 1):
		print("Usage: python classstripper.py <ctags_universal_json_file> - Parse C++ class data contained in Ctags-Universal JSON data into C headers.")
	else:
		print("Parsing Ctags JSON data now.")
		classStripper = CClassStripper() 
		classStripper.Process(sys.argv[1])