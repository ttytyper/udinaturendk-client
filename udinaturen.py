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
import utm
# https://pypi.org/project/gpxpy/
import gpxpy
import gpxpy.gpx
import HTMLParser
import sys

class Udinaturen:
    # Info: https://naturstyrelsen.dk/udinaturen/om-udinaturen/
    # Self documenting API starts here: https://admin.udinaturen.dk/api/v1/?format=json

    root='https://admin.udinaturen.dk/'
    # Delay between requests, to avoid overloading the servers
    # TODO: This only introduces delays when turning pages within the same getAllObjects call, not across separate calls. Fix that
    requestDelay=5
    subCategories={} # Cache subCategories

    def __init__(self,limit=1000):
        # How many objects to fetch per request. The website defaults and limits to 1000
        self.limit=limit
    
    def getAllObjects(self,url):
        next=url
        objects=[]
        while(next!=None):
            eprint("Loading from: %s" % next)
            page=(json.load(urllib.urlopen(next)))
            if("meta" in page and "next" in page["meta"] and page["meta"]["next"]!=None):
                next=self.root + page["meta"]["next"]
                time.sleep(self.requestDelay)
            else:
                next=None
            # Append to the data we've got so far
            objects=list(objects + page["objects"])
        return objects

    def getSubcategories(self):
        if(len(self.subCategories)==0):
            self.subCategories=self.getAllObjects(self.root+'/api/v1/subcategory/?format=json')
        return self.subCategories

class Facilities(Udinaturen):
    facilities=[]
    def getFrom(self,index,name):
        for sid in [sub["id"] for sub in self.getSubcategories() if self.prettyText(sub[index])==name]:
            facilities=self.getFacilities(subCategoryID=sid)
            # TODO: Deduplicate
            self.facilities=list(self.facilities + facilities)

    def getFromMainCategory(self,name):
        self.getFrom(index="maincategory_name",name=name)

    def getFromSubCategory(self,name):
        self.getFrom(index="name",name=name)

    def getFacilities(self,subCategoryID=None):
        if(subCategoryID==None):
            subCategoryID=""
        return self.getAllObjects(url=self.root+'/api/v1/facilityread/?format=json&limit='+str(self.limit)+'&subcategory=' + str(subCategoryID))

    def GPX(self,newLine='\n'):
        # How to do line breaks
        # Some Garmin units prefer "\n", others want "<br />". Viking likes "\n", just not when editing waypoints
        br=newLine
        gpx=gpxpy.gpx.GPX()

        # Prefix for names, to make them stand out from other POIs on a GPS device
        namePrefix="Ud" # Ud(inaturen)

        subCategorySymbols={
            u"Frit teltningsområde": "Forest",
            u"Stor lejrplads":       "Picnic Area",
            u"Lille lejrplads":      "Campground",
            u"Drikkevandspost":      "Drinking water",
            u"Toilet":               "Restrooms"
        }

        attributeFlags={
            u"Drikkevand": "V",
            u"Shelter":    "S"
        }

        for f in self.facilities:
            description=""

            # Extract and convert coordinates
            # Looks like coordinates can be listed as Point or Polygon, in either of these fields
            coord=[]
            for field in ["the_geom","the_geom2"]:
                if(f[field]["type"]=="Point"):
                    coord=f[field]["coordinates"]
                    break
            latlon=utm.to_latlon(coord[0],coord[1],32,'T')

            # Apply appropriate symbols (icons) based on subcategory
            # https://freegeographytools.com/2008/garmin-gps-unit-waypoint-icons-table
            if(f["subcategoryname"] in subCategorySymbols):
                symbol=subCategorySymbols[f["subcategoryname"]]
            else:
                symbol=None

            # Apply descriptions
            description+=br
            if(len(self.prettyText(f["shortdescription"]))>0):
                # No need to show both short and long description if they're identical
                if(self.prettyText(f["shortdescription"]) != self.prettyText(f["longdescription"])):
                    description+=self.prettyText(f["shortdescription"])+br
            if(len(self.prettyText(f["longdescription"]))>0):
                description+=self.prettyText(f["longdescription"])+br

            # Contact info
            description+=br+"Kontaktinfo:"+br
            description+="- Navn: "+self.prettyText(f["organisation"]["name"])+br
            description+="- Telefon: "+self.prettyText(f["organisation"]["telephone"])+br
            description+="- Email: "+self.prettyText(f["organisation"]["email"])+br
            description+="- Link: "+self.prettyText(f["organisation"]["url"])+br

            # List attributes
            if(len(f["attributes"])>0):
                description+=br
                description+="Attributter:"+br
                description+=br.join(['- '+self.prettyText(a["attributename"]) for a in f["attributes"]])

            # Some attributes are so useful that an indicator in the name makes
            # it easier to pick out interesting facilities from a list of their
            # names
            flags=""
            for a in f["attributes"]:
                s=self.prettyText(a["attributename"])
                if(s in attributeFlags):
                    flags+=attributeFlags[s]
            if(f["subcategory"]["webbooking"]):
                flags+='B' # Booking
            if(len(flags)>0):
                flags=' '+flags # Space prefix

            # Direct link to the facility
            description+=br+br
            description+=self.root + f["resource_uri"]+br

            waypoint=gpxpy.gpx.GPXWaypoint(
                latitude=latlon[0],
                longitude=latlon[1],
                name=namePrefix+flags+': '+self.prettyText(f["name"]),
                symbol=symbol,
                # Note: Garmin units only shows comments, not description
                comment=description,
                description=None
            )

            gpx.waypoints.append(waypoint)
        return gpx.to_xml()

    def json(self):
        return self.facilities

    def prettyText(self,text):
        # Many of the fields returned by the servers have odd formatting, such
        # as a ton of trailing spaces. This function removes leading, trailing
        # and consecutive whitespaces (and tabs, line breaks etc), and also
        # tries to turn the HTML into human readable text

        # TODO: Make better use of HTMLParser instead of this unmaintainable bundle of duct tape
        # TODO: Newlines are hardcoded as \n. Don't do that
        html=HTMLParser.HTMLParser()
        return(html.unescape(" ".join(text.split()).replace('<p>','\n').replace('</p>','').replace('<br>','\n').replace('<br />','\n')))

facilities=Facilities()

#facilities.getFromSubCategory(u'Lille lejrplads')
#facilities.getFromSubCategory(u'Stor lejrplads')
#facilities.getFromSubCategory(u'Frit teltningsområde')
#facilities.getFromMainCategory(u'Overnatning')
#facilities.getFromSubCategory(u'Drikkevandspost')
#facilities.getFromSubCategory(u'Toilet')

# Take main and subcategory names from passed arguments
for arg in sys.argv:
    arg=arg.decode('utf-8')
    facilities.getFromMainCategory(arg)
    facilities.getFromSubCategory(arg)

#print(json.dumps(facilities.json()))
print(facilities.GPX())
eprint("Fetched %s facilities" % len(facilities.json()))
