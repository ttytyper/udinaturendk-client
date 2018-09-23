#!/usr/bin/env python
# -*- coding: utf-8 -*-

# For printing to stderr
from __future__ import print_function
import sys
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

import urllib
import json
import time
import xml.etree.cElementTree as ET
import utm
# https://pypi.org/project/gpxpy/
import gpxpy
import gpxpy.gpx
import HTMLParser
html=HTMLParser.HTMLParser()

class Udinaturen:
    # Info: https://naturstyrelsen.dk/udinaturen/om-udinaturen/
    # Self documenting API starts here: https://admin.udinaturen.dk/api/v1/?format=json

    root='https://admin.udinaturen.dk/'

    def getFacilitiesFromMainCategory(self,maincategoryname,limit=1000,maximum=None):
        facilities=[]
        for sid in [sub["id"] for sub in self.getSubcategories() if self.prettyName(sub["maincategory_name"])==maincategoryname]:
            objects=self.getFacilities(limit=limit,maximum=maximum,subcategory=sid)
            facilities=list(facilities + objects)
        return facilities

    def getFacilitiesFromSubCategory(self,subcategoryname,limit=1000,maximum=None):
        facilities=[]
        for sid in [sub["id"] for sub in self.getSubcategories() if self.prettyName(sub["name"])==subcategoryname]:
            objects=self.getFacilities(limit=limit,maximum=maximum,subcategory=sid)
            facilities=list(facilities + objects)
        return facilities

    def getFacilities(self,limit=1000,maximum=None,subcategory=""):
        return self.getAllObjects(maximum=maximum,url=self.root+'/api/v1/facilityread/?format=json&limit='+str(limit)+'&offset=0&subcategory=' + str(subcategory))

    def getSubcategories(self):
        return self.getAllObjects(self.root+'/api/v1/subcategory/?format=json')
    
    def getAllObjects(self,url,maximum=None):
        next=url
        offset=0
        objects=[]
        while(next!=None and (maximum==None or offset<maximum)):
            eprint("Loading from: %s" % url)
            page=(json.load(urllib.urlopen(next)))
            if(page["meta"]["next"]!=None):
                next=self.root + page["meta"]["next"]
                # Avoid DOS'ing the server
                time.sleep(5)
            else:
                next=None
            offset=int(page["meta"]["offset"])
            # Append to the data we've got so far
            objects=list(objects + page["objects"])
        return objects

    def facilitiesToGPX(self,facilities):
        # How to do line breaks
        # Some Garmin units prefer "\n", others want "<br />". Viking doesn't like any of them
        br="\n"

        gpx=gpxpy.gpx.GPX()
        for f in facilities:
            # Looks like coordinates can be listed as Point or Polygon, in either of these fields
            coord=[]
            for field in ["the_geom","the_geom2"]:
                if(f[field]["type"]=="Point"):
                    coord=f[field]["coordinates"]
                    break
            latlon=utm.to_latlon(coord[0],coord[1],32,'T')
            attributes=[]
            for attr in f["attributes"]:
                attributes.append(self.prettyName(attr["attributename"]))
            for attr in f["subcategory"]["attributes"]:
                attributes.append(self.prettyName(attr["attributename"]))
            attributes=sorted(list(set(attributes)))

            # https://freegeographytools.com/2008/garmin-gps-unit-waypoint-icons-table
            symbol=None
            if(f["subcategoryname"]==u"Frit teltningsområde"):
                symbol="Forest"
            elif(f["subcategoryname"]==u"Stor lejrplads"):
                symbol="Picnic Area"
            elif(f["subcategoryname"]==u"Lille lejrplads"):
                symbol="Campground"
            #if(u"Shelter" in attributes):
            #    symbol="Fishing Hot Spot Facility"

            description=self.prettyName(f["subcategoryname"])
            if(u"Shelter" in attributes):
                description+=" med shelter"
            description+=br+br
            if(f["subcategory"]["webbooking"]):
                description+="Booking: Ja"+br
            else:
                description+="Booking: Nej"+br
            if(u"Drikkevand" in attributes):
                description+="Drikkevand: Ja"+br
            else:
                description+="Drikkevand: Nej"+br

            description+=br
            if(len(self.prettyName(f["shortdescription"]))):
                description+=self.prettyName(f["shortdescription"])+br+br
            if(len(self.prettyName(f["longdescription"]))>0):
                description+=self.prettyName(f["longdescription"])+br

            description+=br+"Kontaktinfo:"+br
            description+="- Navn: "+self.prettyName(f["organisation"]["name"])+br
            description+="- Telefon: "+self.prettyName(f["organisation"]["telephone"])+br
            description+="- Email: "+self.prettyName(f["organisation"]["email"])+br
            description+="- Link: "+self.prettyName(f["organisation"]["url"])+br

            description+=br
            description+="Attributer:"+br
            description+=br.join(['- '+s for s in attributes])

            description+=br+br
            description+=self.root + f["resource_uri"]+br

            flags=""
            if(u"Drikkevand" in attributes):
                flags+='V'
            if(u"Shelter" in attributes):
                flags+='S'
            if(f["subcategory"]["webbooking"]):
                flags+='B'
            if(len(flags)>0):
                flags+=': '
            else:
                flags='-: '

            waypoint=gpxpy.gpx.GPXWaypoint(
                latitude=latlon[0],
                longitude=latlon[1],
                name="Ud "+flags+self.prettyName(f["name"]),
                symbol=symbol,
                # Note: Garmin only shows comments, not description
                comment=description,
                description=None
            )

            gpx.waypoints.append(waypoint)
        return gpx

    def prettyName(self,text):
        # Removes leading, trailing and consecutive whitespaces (and tabs, line breaks etc)
        return(html.unescape(" ".join(text.split()).replace('<p>','\n').replace('</p>','')))

udinaturen=Udinaturen()
facilities=udinaturen.getFacilitiesFromMainCategory("Overnatning") #,limit=10,maximum=1)
for f in facilities:
    coord=[]
    for field in ["the_geom","the_geom2"]:
        if(f[field]["type"]=="Point"):
            coord=f[field]["coordinates"]
            break
    latlon=utm.to_latlon(coord[0],coord[1],32,'T')
    eprint("%s: %s (id %s) (%f,%f)" % (
            f["subcategoryname"].strip(),
            f["name"],
            f["facilityid"],
            latlon[0],
            latlon[1]
    ))
eprint("Fetched %s facilities" % len(facilities))

gpx=udinaturen.facilitiesToGPX(facilities)
print(gpx.to_xml())

