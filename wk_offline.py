#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from xml.dom import pulldom
#import html.parser
#parser = html.parser.HTMLParser()

def getText(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)

def get_wk_nodes():
	events = pulldom.parse(sys.stdin)
	try:
		for (event, node) in events:
			if event == pulldom.START_ELEMENT and node.tagName == "page":			
				events.expandNode(node)
				yield node
	except Exception as e:
		sys.stderr.write(str(e)+"\n")


def is_station_article(node):
	for title in node.getElementsByTagName("title"):
		text = getText(title.childNodes)
		if text.find(u"駅")!=-1:
			return True
	return False

def get_child_text(node, childname):
	for title in node.getElementsByTagName(childname):
		return getText(title.childNodes)
	return None

# convert from (degree, minute, second) to decimal degree
def convert_coord(coor):
	coor = tuple(float(x) for x in coor)
	return coor[0] + coor[1]/60 + coor[2]/3600

# get from wikipedia the coordinates of a station given its name
def get_wiki_info(text):
	lon = lat = None
	for line in text.splitlines():
		line = line.strip()
		if line.find("{{aimai}}")!=-1:
			raise Exception("disambiguation page")

		# Detect Mediawiki tagging: |key = value
		if line.startswith("|")==False or line.find("=")==-1:
			continue
		# extract the mediawiki key and value from the line
		# which could be for example:
		# |よみがな = とうきょう
		try:
			key, val = line[1:].split("=", 1)
			key = key.strip()
			val = val.split("&lt;")[0].strip()
			#val = parser.unescape(parser.unescape(val))
		except Exception as e:
			print "x", e
			continue		
		if key==u"座標":
			# example: {{ウィキ座標2段度分秒|34|45|47.43|N|135|31|25.21|E|}}
			fields = val.split("|")
			if len(fields)>=7:
				lat = convert_coord(fields[1:4]) or lat
				lon = convert_coord(fields[5:8]) or lon
		# other coordinate tag which car contain lat or lon, or both
		elif key==u"緯度度" or key==u"経度度":
			pairs = dict(map(lambda x: x.strip(), p.split("=")) for p in line[1:].split("|"))
			lat_fields = (pairs.get(u"緯度度"), pairs.get(u"緯度分"), pairs.get(u"緯度秒"))
			lon_fields = (pairs.get(u"経度度"), pairs.get(u"経度分"), pairs.get(u"経度秒"))
			if None not in lat_fields:
				lat = convert_coord(lat_fields)
			if None not in lon_fields:
				lon = convert_coord(lon_fields)
	# if not lat or not lon:
	# 	print(name, lat, lon)
	return lat, lon


def main():
	wk_nodes = (n for n in get_wk_nodes())
	for node in wk_nodes:
		title = get_child_text(node, "title")
		if not title or title.find(u"駅")==-1:
			continue
		text = get_child_text(node, "text")
		try:
			lat, lon = get_wiki_info(text)
			print u";".join((title, str(lat), str(lon)))
		except Exception as e:
			sys.stderr.write(title+str(e)+"\n")

main()


