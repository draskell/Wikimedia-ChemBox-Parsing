# -*- coding: utf-8 -*-
"""
Author: Drew Gaskell



"""

import xml.etree.cElementTree as ET 
import csv
from pypif import pif
from pypif.obj import Property, ChemicalSystem

# IO files
xml_file = r'C:\Users\###\Downloads\Wikipedia-20161003174511.xml'
out_file = r'C:\Users\###\Desktop\citrine_output_file_v2.csv'
pif_out = r'C:\Users\###\Desktop\citrine_output_PIF_v2.json'
elemental_data_path =  r'C:\Users\###\Desktop\element_data.csv'

# import simple elemental data for checking abreviations
elemental_data = []
with open(elemental_data_path, 'r') as f:
    csv_r = csv.reader(f)
    for row in csv_r:    
        elemental_data.append(row)

# xml tags that are significant
xml_keeper_nodes = {'page':'{http://www.mediawiki.org/xml/export-0.10/}page',
                    'rev':'{http://www.mediawiki.org/xml/export-0.10/}revision',
                    'title':'{http://www.mediawiki.org/xml/export-0.10/}title',
                    'text':'{http://www.mediawiki.org/xml/export-0.10/}text'}           

def text_sections(text):
    '''
    take in chem box text data for a single chemical and break it into sections
    '''
    # split the text into sections
    text = text.split('Section')
    sections = {}
    # make a dictionary of the sections
    for i,section in enumerate(text[1:]):
        sections[i] = section[len(str(i))+1:].replace('{','').replace('}','').replace('[','').replace(']','').split('|')
        sections[i] = [x.strip() for x in sections[i]]
    return sections    
                      
def elements_in_str(string):
    new_string = []    
    for i, part in enumerate(string.split('(')):
        if not len([ch for ch in part if ch.isupper()]) == 0:
            new_string.append(part)
    new_string = ''.join(new_string)
    element_abrev = [e[1] for e in elemental_data]
    uppers = len([ch for ch in new_string if ch.isupper()])
    nums = len([ch for ch in new_string if ch.isdigit()])
    all_num = len(new_string) - nums == 0
    if not all_num and float(uppers)/float(len(new_string)-nums) < 0.5:
        return []
    else:
        contains = []
        for i,char in enumerate(new_string):
            if char.isupper():
                if i+1 == len(new_string):
                    #print 1,char
                    if char in element_abrev:
                        contains.append(char)
                elif new_string[i+1].isupper() or new_string[i+1].isdigit() or new_string[i+1] == ')':
                    #print 2,char
                    if char in element_abrev:
                        contains.append(char)
                elif new_string[i:i+2] in element_abrev:
                    #print 3,string[i:i+2]
                    contains.append(string[i:i+2])
        return contains

def get_chem_formula3(data):
    '''
    find the chemical formula in the text data
    '''
    formula = None
    formula_splitters = [',',
                         '<nowiki>',
                         '.',
                         '<br>',
                         'br',
                         '<br>',
                         'or',
                         'ref',
                         'name',
                         'middot',
                         'sup']  
    formula_replace = [['<sub>',''],['</sub>','']]
    for section in data.values():  
        # step through the sections until we find properties
        if 'Properties' in section[0]:
            # separate the properties into name value pairs ignore section name
            properties = [fields.strip().split('=') for fields in section[1:]]
            # interate the properties
            for i,field in enumerate(properties):
                # check for formula and that the value isn't empty
                if ('Formula' in field[0]) and field[1] and field[1].upper() != 'CHEM':
                    # keep only initial formula for chems with multiple formulae
                    formula = field[1]  
                    for rep in formula_replace:
                        formula = formula.replace(rep[0], rep[1])
                    for splitter in formula_splitters:                    
                        formula = formula.split(splitter)[0]
                    formula = ''.join([ch for ch in formula if ch.isalnum() or ch == '(' or ch == ')'])
                    if not len(elements_in_str(formula)) > 1:
                        formula = None
                # if the initial pass didn't produce a viable formula look in fields after the one with 'Formula' in it
                if not formula and 'Formula' in field[0] and not field[1]:
                    try:
                        # try to find elements from nearby subsequent fields
                        elements = []
                        # in order to keep this section simple only look in the next 4 fields
                        for _ in range(4):
                            if len(elements_in_str(properties[i + _][0])) > 0:
                                element = properties[i + _][0]
                                # if the element isn't in the 'El = #' format this try breaks here
                                count = properties[i + _][1]
                                # if the properties[i + _][1] isn't convertale to an int it breaks here
                                if int(count) == 1:
                                    count = ''
                                elements.append([element,count])
                        formula = ''.join([e[0]+e[1] for e in elements])
                    except:
                        formula = None
                # if neither of the first 2 attempts found a viable formula and there is no Field with 
                #'Formula' to indicate where to look, just look at the first 6 fields
                if not formula and i <= 6 and len(elements_in_str(field[0])) > 0:
                    try:
                        elements = [[field[0],field[1]]]
                        # once the first element is found look ahead to the next 4 values
                        for _ in range(1,5):
                            # if there is an element in the subsequent field add it to the list
                            if properties[i + _][0] in [e[1] for e in elemental_data]:
                                element = properties[i + _][0]                             
                                count = properties[i + _][1]
                                if int(count) == 1:
                                    count = ''
                                elements.append([element,count])
                        
                        formula = ''.join([e[0]+e[1] for e in elements])
                    except:
                        formula = None
    if formula:
        # drop and anhydrous or (x-hydrate) tags
        formula = ''.join([part for part in formula.split('(') if len([ch for ch in part if ch.isupper()]) > 0])
        if len(formula) > 15:
            formula = None
    return formula

def num_ratio(string):    
    '''
    funtion to find the % of a field that is numeric by character. 
    Useful for filtering text where scalars are expected
    '''
    num_cnt = sum(ch.isdigit() for ch in string)
    spaces = sum(ch.isspace() for ch in string)
    if float(len(string) - spaces) == 0:
        return 0
    else:
        return float(num_cnt) / float(len(string) - spaces)

material_data = {}
# read the xml file
doc = ET.parse(xml_file)
# get the doc root
root = doc.getroot()
# step through each 'page'in the wiki media dump
for page in root.iter(xml_keeper_nodes['page']):
    material_data[page.find(xml_keeper_nodes['title']).text] = text_sections(page.find(xml_keeper_nodes['rev']).find(xml_keeper_nodes['text']).text)
    # track chemicals with no data
    # with a more robust formula ID function we could calculate MolarMass for the chemicals with no data
    no_data = [chem for chem,data in material_data.items() if not data]
    # remove empty dicts
    material_data = {chem:data for chem,data in material_data.items() if data}

# fields to ignore
ignore_list = ['VOLUME',
               'ID',
               'ISBN',
               'YEAR',
               'DATE',
               'EDITION',
               'DOI',
               'TITLE',
               'URL',
               'PAGE',
               'PAGES',
               'ACCESSDATE',
               'TITLE',
               'ISSUE',
               'ISSN',
               'BIBCODE',
               'ORIGYEAR',
               'WEBSITE',
               'JOURNAL',
               'ZVG',
               'WORK']
   
non_num_checks = ['AUTH',
                  'PUBLI',
                  'CITE',
                  'FIRST',
                  'LAST']
               
# fields to trim after
split_by = ['<ref>',
            '<ref',
            '<br>',
            ',',
            '<br/>']
# html entities to replace
rep_with = [['&nbsp;', ' '],
            ['&minus;','-'],
            ['</sup>',''],
            ['<sup>','^'],
            [']',''],
            ['[',''],
            ['(',''],
            [')',''],
            ['&thinsp;','']]
# expected fields short list to save a few data points
common_fields = {'MolarMass': 'g/mol',
                 'Density': 'g/cm^3',}

letter_list = set('abcdefghijklmnopqrstuvwxy ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789')

all_dat = []
#process the data
property_dict = {}
for chem, data in material_data.iteritems():
    # get the formula
    formula = get_chem_formula3(data)
    properties = []
    # step through the data for each wiki entry
    for section, fields in data.iteritems():
        # only parsing data from the properties and thermochemistry sections because the data in these sections
        # conforms to the desired output
        if 'Properties' in fields[0] or 'Thermochemistry' in fields[0]:
            # only taking fields that have an equality and are less than 100 characters long, again because of the
            # desired type of data.
            properties.extend([field.strip().split('=') for field in fields[1:] if '=' in field and len(field) < 100])
            # filtering data to remove entries with only text where we expect scalar values 
            properties = [prop for prop in properties if len(prop[1]) > 3]# and num_ratio(prop[1]) > 0]  
            # skipping the Formula field because it has already been read
            properties = [prop for prop in properties if "Formula" not in prop[0]]
            
            property_data = {}            
            for prop in properties:
                # only process properties that are not in the ignore list
                if (prop[0].strip().upper() not in ''.join(ignore_list)) and ('NOTES' not in prop[0].strip().upper()):
                    value = prop[1].strip()
                    # remove unwanted strings at the end of the value
                    for splitter in split_by:
                        value = value.split(splitter)[0]
                    # remove web related cahracters
                    for replacement in rep_with:
                        value = value.replace(replacement[0], replacement[1])
                    # add units to boiling/melting point values
                    if 'PtC' in prop[0]:
                        value = value + ' C'
                    if 'PtK' in prop[0]:
                        value = value + ' K'
                    # remove leading text                    
                    num_indices = []                    
                    for i,ch in enumerate(value):
                        if ch.isdigit() or ch == '-':
                            num_indices.append(i)
                    # remove non-ascii characters
                    value = value.encode('ascii','ignore')
                    # ignores leading strings in numeric
                    if not num_indices:
                        property_data[prop[0].strip()] = value
                    else:
                        value = value[min(num_indices):]
                        property_data[prop[0].strip()] = value

    # if a formula is found
    if formula:       
        for name, prop in property_data.items():
            # check if the property is numeric
            if num_ratio(prop.split(' ', 1)[0]) > 0.5:
                split = prop.split(' ', 1)
                # check if the property splits to scalar and units
                if num_ratio(split[0]) > 0.5:    
                    # if the field has units
                    if len(split) > 1:
                        all_dat.append([formula,name.encode('ascii','ignore'),split[0].encode('ascii','ignore'),split[1].encode('ascii','ignore')])
                    # if the field doesn't have units the units can be added for common fields
                    elif split[0].strip() in common_fields.keys():
                        all_dat.append([formula,name.encode('ascii','ignore'),split[0].encode('ascii','ignore'),common_fields[split[0]]])
                    else:
                        # catch numeric data without units
                        all_dat.append([formula,name.encode('ascii','ignore'),split[0].encode('ascii','ignore'),'NoUnits'])
            else:
                # catch data that is not numeric
                # check if it relates to the publication of the source
                if len([check for check in non_num_checks if check in name.upper()]) == 0:
                    #strip all the non-alphanumeric characters but leave spaces                    
                    prop = ''.join(filter(letter_list.__contains__, prop))
                    all_dat.append([formula,name.encode('ascii','ignore'),prop.encode('ascii','ignore'),'NoUnits'])

# write the csv
with open(out_file, 'w') as f:
    writer = csv.writer(f)
    writer.writerows(all_dat)

# from the documentation I'm not 100% that this is the preferred usage of the ChemicalSystem object
# or that the data is being put out in the desired way, but it's a first stab. 
with open(pif_out, 'w') as f:
    for chem in set([datum[0] for datum in all_dat]):
        chem_system = ChemicalSystem()
        chem_system.chemical_formula = chem
        prop_list = []
        for data in [datum for datum in all_dat if datum[0] == chem]:
            prop_list.append(Property(name=data[1],scalar=data[2],units=data[3]))
        chem_system.properties = prop_list
        f.write(pif.dumps(chem_system))