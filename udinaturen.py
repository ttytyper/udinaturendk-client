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

class Udinaturen:
    # Info: https://naturstyrelsen.dk/udinaturen/om-udinaturen/
    # Self documenting API starts here: https://admin.udinaturen.dk/api/v1/?format=json

    root='https://admin.udinaturen.dk/'
    # Delay between requests, to avoid overloading the servers
    # TODO: This only introduces delays when turning pages within the same getAllObjects call, not across separate calls. Fix that
    requestDelay=5

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
        return self.getAllObjects(self.root+'/api/v1/subcategory/?format=json')

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

    # TODO: This function is a bit messy and interely focused on camping facilites. Clean it up and make it more generic
    def GPX(self,newLine='\n'):
        # How to do line breaks
        # Some Garmin units prefer "\n", others want "<br />". Viking doesn't like any of them
        br=newLine
        gpx=gpxpy.gpx.GPX()

        for f in self.facilities:
            # Looks like coordinates can be listed as Point or Polygon, in either of these fields
            coord=[]
            for field in ["the_geom","the_geom2"]:
                if(f[field]["type"]=="Point"):
                    coord=f[field]["coordinates"]
                    break
            latlon=utm.to_latlon(coord[0],coord[1],32,'T')

            attributes=[]
            for attr in f["attributes"]:
                attributes.append(self.prettyText(attr["attributename"]))
            attributes=sorted(list(set(attributes))) # Sort and deduplicate

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

            # Attributes of particular interest are listed early in the description
            description=self.prettyText(f["subcategoryname"])+br
            if(u"Shelter" in attributes):
                description+="Shelter: Ja"+br
            if(f["subcategory"]["webbooking"]):
                description+="Booking: Ja"+br
            else:
                description+="Booking: Nej"+br
            if(u"Drikkevand" in attributes):
                description+="Drikkevand: Ja"+br
            else:
                description+="Drikkevand: Nej"+br

            description+=br
            if(len(self.prettyText(f["shortdescription"]))):
                description+=self.prettyText(f["shortdescription"])+br+br
            if(len(self.prettyText(f["longdescription"]))>0):
                description+=self.prettyText(f["longdescription"])+br

            description+=br+"Kontaktinfo:"+br
            description+="- Navn: "+self.prettyText(f["organisation"]["name"])+br
            description+="- Telefon: "+self.prettyText(f["organisation"]["telephone"])+br
            description+="- Email: "+self.prettyText(f["organisation"]["email"])+br
            description+="- Link: "+self.prettyText(f["organisation"]["url"])+br

            description+=br
            description+="Attributer:"+br
            description+=br.join(['- '+s for s in attributes])

            description+=br+br
            description+=self.root + f["resource_uri"]+br

            # Some attributes are so useful that an indicator in the name makes
            # it easier to pick out interesting facilities from a list of their
            # names
            flags=""
            if(u"Drikkevand" in attributes):
                flags+='V' # Vand
            if(u"Shelter" in attributes):
                flags+='S' # Shelter
            if(f["subcategory"]["webbooking"]):
                flags+='B' # Booking
            if(len(flags)>0):
                flags+=': ' # End of flags
            else:
                flags='-: ' # No interestring attributes

            # Prefix for names, to make them stand out from other POIs on a GPS device
            namePrefix="Ud " # Ud(inaturen)

            waypoint=gpxpy.gpx.GPXWaypoint(
                latitude=latlon[0],
                longitude=latlon[1],
                name=namePrefix+flags+self.prettyText(f["name"]),
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
facilities.getFromMainCategory(u'Overnatning')

print(facilities.GPX())
eprint("Fetched %s facilities" % len(facilities.json()))
