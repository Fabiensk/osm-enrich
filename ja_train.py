#!/usr/bin/python3
#
# Copyright 2012 F a b i e n  SK
# Contact : fabsk [.at.] free.fr

# Licensed under the BSD license (see LICENSE.TXT)

from xml.dom import pulldom
import xml.parsers.expat
import sys, sysconfig
import time
import math
import os.path
import urllib
from ja_train_download import get_wiki_info, get_wiki_info_offline, download_page

# each OSM file will contain this number of stations
BATCH_SIZE = 200
# logs details about each station
logger = None

# only compatible with Python 3, but it may be usefull one day
is_py3 = sysconfig.get_python_version().split(".")[0]=="3"

if is_py3:
	from urllib.parse import quote, unquote
	myunquote = unquote
else:
	from urllib import unquote
	myunquote = lambda x: unquote(str(x))

# read an input stream or string and return XML nodes as a generator
def get_nodes_from_xml(src):
	if type(src)==str:
		events = pulldom.parseString(src)
	else:
		# file like object
		events = pulldom.parse(src)
	try:
		for (event, node) in events:
			if event == pulldom.START_ELEMENT and node.tagName == "node":			
				events.expandNode(node)
				yield node
	except Exception as e:
		print(e, file=sys.stderr)

# add a tag to a OSM XML node (tag does not exist yet)
def add_tag(node, tag, val):
	new = node.ownerDocument.createElement("tag")
	new.setAttribute("k", tag)
	new.setAttribute("v", val)
	node.appendChild(new)

# data and manipulation methods for a station
class Station:
	def __init__(self, node):
		# associated XML node
		self.node = node
		# map: osm tag name -> (value, xm node)
		self.tags = dict((tag_node.getAttribute("k"), (tag_node.getAttribute("v"), tag_node)) for tag_node in node.getElementsByTagName("tag"))
	# return a tag value (or None)
	def get_tag(self, key):
		val = self.tags.get(key)
		return val[0] if val else None
	def __repr__(self):
		return self.node.getAttribute("id")
	def str(self):
		return self.get_tag("name:ja") or self.node.getAttribute("id") or self.node.toxml()
	def str_old(self):		
		return self.str().encode("utf-8")
	__str__ = str if is_py3 else str_old
	def has_wiki(self):
		return self.get_tag("wikipedia")!=None
	def id(self):
		return self.node.getAttribute("id")
	def xml(self):
		return self.node.toxml("utf-8")
	def lat(self):
		return float(self.node.getAttribute("lat"))
	def lon(self):
		return float(self.node.getAttribute("lon"))
	# check if the wikipedia data has to be completed
	def is_valid(self):
		wk = self.get_tag("wikipedia")
		if wk==None or wk.startswith("ja:")==False:
			return False
		for k in self.tags.keys():
			if k.startswith("wikipedia") and k!="wikipedia":
				return False
		return True
	# modify the XML node
	def fix(self):
		modified = False
		wk = self.get_tag("wikipedia")
		wk_ja_pair = self.tags.get("wikipedia:ja")
		# convert tag (wikipedia:ja -> URL) to tag (wikipedia -> ja:name)
		if wk==None:
			if wk_ja_pair!=None and wk_ja_pair[0].startswith("http://ja.wikipedia.org"):
				page_name = wk_ja_pair[0].split("/")[-1]
				# unquote if necessary
				if page_name.startswith("%"):
					page_name = myunquote(page_name)
				add_tag(self.node, "wikipedia", "ja:"+page_name)
				wk_ja_pair[1].parentNode.removeChild(wk_ja_pair[1])
				modified = True
				logger.write("{0}:fixed from previous format\n".format(page_name))
			if wk_ja_pair!=None and wk_ja_pair[0].startswith("ja:"):
				page_name = wk_ja_pair[0]
				# unquote if necessary
				add_tag(self.node, "wikipedia", page_name)
				wk_ja_pair[1].parentNode.removeChild(wk_ja_pair[1])
				modified = True
				logger.write("{0}:fixed from previous format 2\n".format(page_name))
			else:
				modified = self.fix_new_tag()
		# update the modified flag if needed
		if modified:
			self.node.setAttribute("action", 'modify')
	def fix_new_tag(self):
		# try to find the japanese name
		kanji = self.get_tag("name:ja")
		if kanji==None or len(kanji)==0:
			# try with generic tag, but accept only those with only japanese characters
			kanji = self.get_tag("name")
			if kanji==None:
				return False
			# if the name contains also a kana name or romaji name, remove it
			kanji = kanji.split("(")[0]
			kanji = kanji.split("（")[0].strip()
			if len(kanji)==0:
				return False
			for c in kanji:
				# check that we only have only japanese characters
				# kanji or kana
				if not( (ord(c)>=0x3400 and ord(c)<=0x9FFF) or (ord(c)>=0x3040 and ord(c)<=0x30FF) ):
					return False

		# add 駅 to make a wikipedia name
		if kanji[-1]!="駅":
			kanji += "駅"

		# compare wikipedia and openstreetmap location to be sure
		try:
			# lat, lon = get_wiki_info(kanji)
			lat = lon = None
			matches_nearby = []
			distances = []
			matches_all = get_wiki_info_offline(kanji)
			for match in matches_all:
				dist = distance( (self.lat(), self.lon()), match[:2])
				distances.append(dist)
				if dist<0.5:
					matches_nearby.append(match)
			if len(matches_nearby)==1:
				lat, lon, new_kanji = matches_nearby[0]
				if kanji!=new_kanji:
					print("{0} -> {1}".format(kanji, new_kanji))
				kanji = new_kanji

			if lat and lon:
				dst = distance((float(lat), float(lon)), (self.lat(), self.lon()))
				# let's say that it is of if within 500 meters
				if dst<0.5:
					add_tag(self.node, "wikipedia", "ja:"+kanji)
					logger.write("{0}:added, distance={1:f}\n".format(kanji, dst))
					return True
				else:
					logger.write("{0}:not added, distance={1:f}\n".format(kanji, dst))
			else:
				logger.write("{0}:not added, no unique match: {1}/{2};{3}\n".format(kanji, len(matches_nearby),
																		 len(matches_all),
																		 ",".join(map(str, distances))))
		except Exception as e:
			logger.write("{0}:not added, {1}\n".format(kanji, e.args))

		return False
		
# try to group stations in the same neighborhood
def sort_lon(lst):
	if is_py3:
		lst.sort(key=lambda x: x.lon())
	else:
		lst.sort(lambda x, y: cmp(x.lon(), y.lon()))

def sort_lat(lst):
	if is_py3:
		lst.sort(key=lambda x: x.lat())
	else:
		lst.sort(lambda x, y: cmp(x.lat(), y.lat()))

def distance(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371 # km

    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = radius * c

    return d

# recurively form groups of stations in the same neighboorhood
# simple algo, but it works
def group_geo(stations):
	# small enough to form a group
	if len(stations)<BATCH_SIZE:
		return [stations]
	# find if longer in latitude or longitude
	min_lat = max_lat = stations[0].lat()
	min_lon = max_lon = stations[0].lon()
	for st in stations:
		min_lat = min(min_lat, st.lat())
		max_lat = max(max_lat, st.lat())
		min_lon = min(min_lon, st.lon())
		max_lon = max(max_lon, st.lon())
	# sort the longest side
	dlon = distance((min_lat, min_lon), (min_lat, max_lon))
	dlat = distance((min_lat, min_lon), (max_lat, min_lon))
	if dlon>dlat :
		sort_lon(stations)
	else:
		sort_lat(stations)
	mid = len(stations)//2
	return group_geo(stations[:mid]) + group_geo(stations[mid:])

# correct group
def process_group(idx, grp):
	# update from OSM server
	ids = ",".join([st.id() for st in grp])
	url = "http://api.openstreetmap.org/api/0.6/nodes?nodes=" + ids
	xml = download_page(url).decode("utf-8")
	new_nodes = get_nodes_from_xml(xml)
	# print(list(new_nodes))
	new_stations = list(Station(node) for node in new_nodes)

	# process
	with open(os.path.join("out", "group_{0:04d}.xml".format(idx)), "wt") as f:
		f.write("""<?xml version='1.0' encoding='UTF-8'?><osm version='0.6' upload='true' generator='JOSM'>""")
		for station in new_stations:
			station.fix()
			station.node.writexml(f)
		f.write("</osm>")
		
# main
def main():
	global logger
	logger = open("train.log", "wt")
	gen_nodes = get_nodes_from_xml(sys.stdin)
	gen_stations = (Station(node) for node in gen_nodes)
	gen_stations_ok = (station for station in gen_stations if station.is_valid()==False)
	stations_ok = list(gen_stations_ok)
	stations_groups = group_geo(stations_ok)
	group_idx = 0
	while len(stations_groups)>0:
		grp = stations_groups[0]
		del stations_groups[0]
		process_group(group_idx, grp)
		group_idx += 1


main()
