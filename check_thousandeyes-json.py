#!/usr/bin/python

import sys
import re
import urllib2
import ConfigParser
import socket
import os
import json
import operator
from xml.dom.minidom import parseString
from optparse import OptionParser, OptionGroup
from string import Template

def s2s(s):
    """ return empty string for None. return the argument otherwise """
    if (s is None): return ""
    else: return s

class TestMetric(object):
    def __init__(self, id, enabled, name, interval, url, **kwargs):
        self.id = id
        self.enabled = enabled
        self.name = name
        self.interval = interval
        self.url = url        

class Test(object):
    def __init__(self, id, enabled, uri, name, interval, url):
        self.id = id
        self.enabled = enabled
        self.uri = uri
        self.name = name
        self.interval = interval
        self.url = url
        
class Alert(object):
    def __init__(self, id, name, active, uri, link, datestart, dateend):
        self.id = id
        self.name = name
        self.active = active
        self.uri = uri
        self.link = link
        self.datestart = datestart
        self.dateend = dateend

class TestLocation(object):
    def __init__(self, testid, countryid, location, permalink, testdate, resp, domload, pageload, errors):
        self.testid = testid
        self.countryid = countryid
        self.location = location
        self.permalink = permalink
        self.testdate = testdate
        self.resp = resp
        self.domload = domload
        self.pageload = pageload
        self.errors = errors

class TestLocationCollection(object):
    def __init__(self):
        self._testlocation = {}

    def __getitem__(self, tl):
        return self._testlocation[tl]
        
    def __iter__(self):
        return self._testlocation.__iter__()

    def add(self, tl):
        self._testlocation[tl.countryid]=tl

    def list(self):
        for i in sorted(self, reverse=False):
            n = ({'testId': self[i].id, 'countryId': self[i].countryid, 'locationName': self[i].location, 'permalink': self[i].permalink, 'date': self[i].testdate, 'responseTime': self[i].resp, 'domLoadTime': self[i].domload, 'pageLoadTime': self[i].pageload, 'numErrors': self[i].errors})
        print n
            
class TestCollection(object):
    def __init__(self):
        self._tests = {}
        
    def __getitem__(self, t):
        return self._tests[t]
        
    def __iter__(self):
        return self._tests.__iter__()

    def add(self, t):
        self._tests[t.id]=t
        
    def list(self):
        t = """| %6s | %1s | %-16s | %-64s | %-8s | %-48s |"""
        heading = t % ("ID", "E", "Type", "Name", "Interval", "Resource")
        line = "-" * len(heading)
        print "List of Tests\n"
        print line
        print heading
        print line
        for i in sorted(self):
            enabled = self[i].enabled
            if (enabled):
                en = "Y"
            else:
                en = "N"
            print t % (self[i].id, en, self[i].uri, self[i].name, self[i].interval, self[i].url)
        print line

    def listid(self):
        for i in sorted(self):
            return list(self[i].id)

    def listjson(self):
        for i in sorted(self, reverse=True):
            print json.dumps({'id': self[i].id, 'active': self[i].enabled, 'type': self[i].uri, 'name': self[i].name, 'interval': self[i].interval, 'resource': self[i].url}, indent=2, separators=(',', ': '))


class AlertCollection(object):
    def __init__(self):
        self._alerts = {}
        
    def __getitem__(self, a):
        return self._alerts[a]
        
    def __iter__(self):
        return self._alerts.__iter__()

    def add(self, a):
        self._alerts[a.id]=a
        
    def list(self):
        a = """| %6s | %-40s | %-7s | %-16s | %-68s | %-19s | %-19s |"""
        heading = a % ("ID", "Name", "Active", "Type", "Permalink", "Start (UTC)", "End (UTC)")
        line = "-" * len(heading)
        print "List of Alerts\n"
        print line
        print heading
        print line
        for i in sorted(self, reverse=True):
            active = self[i].active
            if (active):
                ac = "Active"
            else:
                ac = "Expired"
            print a % (self[i].id, self[i].name, ac, self[i].uri, self[i].link, self[i].datestart, self[i].dateend)
        print line

    def listjson(self):
        for i in sorted(self, reverse=True):
            print json.dumps({'id': self[i].id, 'name': self[i].name, 'active': self[i].active, 'type': self[i].uri, 'permalink': self[i].link, 'datestart': self[i].datestart, 'dateend': self[i].dateend  }, indent=2, separators=(',', ': '))


class Endpoint(object):

    test_types = { "basic-http": "web/basic-http" , "dns-server": "dns/server", "dns-dnssec": "dns/dnssec", "page-load": "web/page-load", "transactions": "web/transaction", "network": "net/metrics", "bgp": "net/bgp-metrics" }
    alert_types = { "basic-http": "web/basic-http" , "dns-server": "dns/server", "dns-dnssec": "dns/dnssec", "dns-trace": "dns/trace", "page-load": "web/page-load", "transactions": "web/transaction", "network": "net/metrics", "bgp": "net/bgp-metrics", "dnsp-domain": "DNS+ Domain", "dnsp-server": "DNS+ Server", "uxm": "User Experience" }      

    def __init__(self, endpoint, token, window):
        self.api_token = token
        self.api_endpoint = endpoint
        self.window = window

    def fetch(self, uri):
            req = urllib2.Request(self.api_endpoint + uri + ".json?authToken=" + self.api_token + "&window=" + self.window)
            timeout=60
            socket.setdefaulttimeout(timeout)
            try:
                sock=urllib2.urlopen(req)
            except urllib2.URLError, e:
                return None
            teResponse = sock.read()
            sock.close()
            jsonResponse = json.loads(teResponse)
            return jsonResponse
 

    def get_tests(self):
        tests = TestCollection()
        for i in self.test_types.keys():
            t = self.fetch("/tests/" + i)
            if (t is None):
                continue
            for test in t['test']:
                t_id = test['testId']
                t_enabled = test['enabled']
                t_name = test['testName']
                if (i == "dns-server" or i == "dns-dnssec"):
                    t_url = test['domain']
                elif (i == "network"):
                    t_url = test['server']
                elif (i == "bgp"):
                    t_url = test['prefix']
                    t_interval = '-'
                else:
                    t_url = test['url']
                    t_interval = test['interval']
                test = Test(t_id, t_enabled, i, t_name, t_interval, t_url)
                tests.add(test)
        return tests


    def get_alerts(self):
        alerts = AlertCollection()
        for i in self.alert_types.keys():
            a = self.fetch("/alerts/" + i)
            if (a is None):
                continue
            for alert in a['alert']:
                a_id = alert['alertId']
                a_active = alert['active']
                a_name = alert['testName']
                a_link = alert['permalink']
                a_start = alert['dateStart']
                a_end = alert['dateEnd']
                for location in alert['locations']:
                    al_id = alert['alertId']
                    al_locationname = location['locationName']
                    al_active = location['active']
                location = Location(al_id, al_locationname, al_active)
                alert = Alert(a_id, a_name, a_active, i, a_link, a_start, a_end)
                alerts.add(alert)
        return alerts
        
                            
class Agent(object):
    def __init__(self, endpoint, typ, id):
        self.endpoint = endpoint
        self.id = id
        self.typ = typ
    def _fetch(self):
		jsonResponse = self.endpoint.fetch("/" + self.endpoint.test_types[self.typ] + "/" + str(self.id))
		if self.typ == "basic-http" or self.typ == "page-load" or self.typ == 'transaction':
			if not jsonResponse['web']['test'] is None:
				self.testname = jsonResponse['web']['test']['testName']
				self.enabled = int(jsonResponse['web']['test']['enabled'])
				return jsonResponse
		elif self.typ == 'network':
			if not jsonResponse['net']['test'] is None:
				self.testname = jsonResponse['net']['test']['testName']
				self.enabled = int(jsonResponse['net']['test']['enabled'])
				return jsonResponse
		else:
			return None
        
    def check(self):
        raise NotImplementedError("Agent is an abstract class")

class HttpBasicAgent(Agent):
    def __init__(self, endpoint, id):
        super(self.__class__, self).__init__(endpoint, "basic-http", id)

    def check(self):
        jsonResponse = self._fetch()
        if (jsonResponse is None):
            print "Empty Result Set"
        failed = 0
        over = 0
        count = 0
        sum = 0
        for testResult in jsonResponse['web']['basicHttp']:
            code = int(testResult['responseCode'])
            resp = int(testResult['responseTime'])
            loc = testResult['locationName']
            if (code!=200): failed += 1
            count += 1
            sum += resp
        if (count>0):
            avg = sum/count
        else:
            avg = 0
        if (self.enabled==0):
            msg = " DISABLED"
        else:
            msg = " Average HTTP Time %.2f, Failed %d, Exceed threshold %d" % (avg, failed, over)
        n = ("basic-http %s " % (self.testname + msg))
        return n

class PageLoadAgent(Agent):
    def __init__(self, endpoint, id):
        super(self.__class__, self).__init__(endpoint, "page-load", id)

    def check(self):
        jsonResponse = self._fetch()
        locations = TestLocationCollection()
        if (jsonResponse is None):
            print "Empty Result Set"
        for testResult in jsonResponse['web']:
            tl_testid = int(testResult['test']['testId'])
            tl_countryid = testResult['pageLoad']['countryId']
            tl_loc = testResult['pageLoad']['locationName']
            tl_date = testResult['pageLoad']['date']
            tl_permalink = testResult['pageLoad']['permalink']
            tl_resp = int(testResult['pageLoad']['responseTime'])
            tl_domload = int(testResult['pageLoad']['domLoadTime'])
            tl_pageload = int(testResult['pageLoad']['pageLoadTime'])
            tl_errors = int(testResult['pageLoad']['numErrors'])
            location = TestLocation(tl_testid, tl_countryid, tl_loc, tl_permalink, tl_date, tl_resp, tl_domload, tl_pageload, tl_errors)
            locations.add(location)
        l = locations.list()
        return l
        

class NetPerfAgent(Agent):
    def __init__(self, endpoint, id):
        super(self.__class__, self).__init__(endpoint, "network", id)
        
    def check(self):
        jsonResponse = self._fetch()
        if (jsonResponse is None):
            print "Empty Result Set"
        count = 0
        avg_lat = 0
        avg_loss = 0
        over_time = 0
        over_loss = 0
        for testResult in jsonResponse['net']['metrics']:
            loss = float(testResult['loss'])
            maxl = float(testResult['maxLatency'])
            avgl = float(testResult['avgLatency'])
            count += 1
            avg_lat += avgl
            avg_loss += loss
        if (count>0):
            avg_lat = avg_lat/count
            avg_loss = avg_loss/count 
        else:
            msg = " Average Latency %.2f, Average Loss %.2f" % (avg_lat, avg_loss)
        
        print "avg_latency", avg_lat, "ms"
        print "avg_loss", avg_loss
        print "failed_latency", over_time
        print "failed_loss", over_loss
                         
    
def main():
    usage="usage: %prog [-h|--help] [-c|--config Config-File] list-tests|list-alerts|get-stats [-w|--window seconds] [-H|--host test-id]"
    parser=OptionParser(usage=usage, version="%prog 0.1")
    parser.add_option("-c", "--config", dest="cf", help="Configuration File")
    parser.add_option("-H", "--host", dest="testid", type="int", help="Test ID")
    parser.add_option("-t", "--type", dest="type", help="Test Type")
    parser.add_option("-w", "--window", dest="window", help="Alert Window")
    parser.add_option("-j", "--json", action="store_true", dest="jsonoutput", default=False, help="Output in JSON Format")
    (options, args) = parser.parse_args()
    
    if (len(args)==0):
        parser.error("Command required")
    if (options.cf):
        config_file = options.cf
    else:
        config_file = "check_thousandeyes.conf"

    config = ConfigParser.ConfigParser()
    config.read(config_file)
    api_token=config.get("API", "token")
    api_endpoint=config.get("API", "endpoint")
    if (options.window):
        window = options.window
    else:
        window="0"
    e = Endpoint(api_endpoint, api_token, window)
    if (args[0]=='list-tests'):
        tests = e.get_tests()
        if (options.jsonoutput==True):
            tests.listjson()
        else:
            tests.list()
    elif (args[0]=='list-alerts'):
        alerts = e.get_alerts()
        if (options.jsonoutput==True):
            alerts.listjson()
        else:
            alerts.list()
    elif (args[0]=='get-stats'):
        if (options.type):
            test_type = options.type
        else:
            test_type = "page-load"              
        tests = e.get_tests()
        if (test_type == "basic-http"):
            a = HttpBasicAgent(e, tid)
            n = a.check()
            print n
        elif (test_type == "page-load"):
            if (options.testid):
                tid = options.testid
                a = PageLoadAgent(e, tid)
                n = a.check()
                print n
            else:
                tests = e.get_tests()
                for i in tests.listid():
                    a = PageLoadAgent(e, i)
                    n = a.check()
                print n
                
        elif (test_type == "net-perf"):
            a = NetPerfAgent(e, tid)
            n = a.check()
            print n
        else:
            parser.error("Invalid command")       

if __name__ == '__main__':     
     main()