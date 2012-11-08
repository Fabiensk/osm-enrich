# Copyright 2012 F a b i e n  SK
# Contact : fabsk [.at.] free.fr

# Licensed under the BSD license (see LICENSE.TXT)

import sys
from urllib.parse import quote
import os.path
import urllib, urllib.request
import html.parser
parser = html.parser.HTMLParser()

offline = {}

def load_offline():
	for line in open("offline.txt"):
		name, lat, lon = line.strip().split(";")
		lat = float(lat)
		lon = float(lon)
		pos = name.index("駅")
		key = name[:pos+1]
		offline.setdefault(key, []).append((lat, lon, name))

def debug(*args):
	pass

# return the content of a page given its URL
def download_page(url):
	print(url, file=sys.stderr)
	opener = urllib.request.build_opener()
	# required for wikipedia
	opener.addheaders = [('User-agent', 'Mozilla/5.0')]
	return opener.open(url).read()

# get a page from an URL or from the local cache in directory "wiki"
def get_page_with_cache(name, url):
	ret = {}
	path = os.path.join("wiki", name)		
	try:
		return open(path, "rt").read()
		# os.stat(path)
	except:
		content = download_page(url)
		f = open(path, "wb")
		f.write(content)
		return content.decode()

# convert from (degree, minute, second) to decimal degree
def convert_coord(coor):
	coor = tuple(float(x) for x in coor)
	return coor[0] + coor[1]/60 + coor[2]/3600

# get from wikipedia the coordinates of a station given its name
def get_wiki_info(name):
	url = "http://ja.wikipedia.org/w/index.php?title={0}&action=edit".format(quote(name))
	data = get_page_with_cache("edit_"+name, url)
	inside_textarea = False
	lon = lat = None
	# for each line
	for line in data.splitlines():
		# make sure that we only analyze inside the textarea
		if inside_textarea==False:
			if line.find("<textarea")!=-1:
				inside_textarea = True
			continue
		line = line.strip()
		# after this mark, no interesting data
		if line.find("</textarea")!=-1:
			inside_textarea = False
			continue

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
			val = parser.unescape(parser.unescape(val))
		except Exception as e:
			continue
		if key=="座標":
			# example: {{ウィキ座標2段度分秒|34|45|47.43|N|135|31|25.21|E|}}
			fields = val.split("|")
			if len(fields)>=7:
				lat = convert_coord(fields[1:4]) or lat
				lon = convert_coord(fields[5:8]) or lon
		# other coordinate tag which car contain lat or lon, or both
		elif key=="緯度度" or key=="経度度":
			pairs = dict(map(lambda x: x.strip(), p.split("=")) for p in line[1:].split("|"))
			lat_fields = (pairs.get("緯度度"), pairs.get("緯度分"), pairs.get("緯度秒"))
			lon_fields = (pairs.get("経度度"), pairs.get("経度分"), pairs.get("経度秒"))
			if None not in lat_fields:
				lat = convert_coord(lat_fields)
			if None not in lon_fields:
				lon = convert_coord(lon_fields)
	# if not lat or not lon:
	# 	print(name, lat, lon)
	return lat, lon

def get_wiki_info_offline(name):
	if name[-1]!="駅":
		name += "駅"
	return offline.get(name) or tuple()

load_offline()

if __name__=="__main__":
	def debug(*param):
		print(*param)
	for name in sys.argv[1:]:
		# print(get_wiki_info(name))
		for res in get_wiki_info_offline(name):
			print(res)

