#!/usr/bin/env python
PROGRAM_NAME = "cg-site-health-check.py"
PROGRAM_DESCRIPTION = """
CloudGenix script
---------------------------------------


"""
from cloudgenix import API, jd
import os
import sys
import argparse
from fuzzywuzzy import fuzz
from datetime import datetime,timedelta   
import numpy as np
import requests 
import json
from lxml import html
import cloudgenix_idname
import cloudgenix_settings


####################################################################
# Read cloudgenix_settings file for auth token or username/password
####################################################################

sys.path.append(os.getcwd())
try:
    from cloudgenix_settings import CLOUDGENIX_AUTH_TOKEN

except ImportError:
    # Get AUTH_TOKEN/X_AUTH_TOKEN from env variable, if it exists. X_AUTH_TOKEN takes priority.
    if "X_AUTH_TOKEN" in os.environ:
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('X_AUTH_TOKEN')
    elif "AUTH_TOKEN" in os.environ:
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
    else:
        # not set
        CLOUDGENIX_AUTH_TOKEN = None

try:
    from cloudgenix_settings import CLOUDGENIX_USER, CLOUDGENIX_PASSWORD

except ImportError:
    # will get caught below
    CLOUDGENIX_USER = None
    CLOUDGENIX_PASSWORD = None


print_console = True
print_pdf = False


dns_trt_thresholds = {
    'fail': 120,
    'warn': 50
}

CLIARGS = {}
cgx_session = API(update_check=False)              #Instantiate a new CG API Session for AUTH
diff_hours = 24              #Hours to look back at

pan_service_dict = {
                "Prisma Access": 'q8kbg3n63tmp',
                "Prisma Cloud Management": "61lhr4ly5h9b",
                "Prisma Cloud": '1nvndw0xz3nd',
                "Prisma SaaS": 'f0q7vkhppsgw',
}

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
def pBold(str_to_print):
    return(bcolors.BOLD + str_to_print + bcolors.ENDC)
def pFail(str_to_print):
    return(bcolors.FAIL + str_to_print + bcolors.ENDC)
def pPass(str_to_print):
    return(bcolors.OKGREEN + str_to_print + bcolors.ENDC)
def pWarn(str_to_print):
    return(bcolors.WARNING + str_to_print + bcolors.ENDC)
def pExceptional(str_to_print):
    return(bcolors.OKBLUE + str_to_print + bcolors.ENDC)
def pUnderline(str_to_print):
    return(bcolors.UNDERLINE + str_to_print + bcolors.ENDC)
def dns_trt_classifier(dns_trt_time):
    if( dns_trt_time > dns_trt_thresholds['fail']):
        return str(dns_trt_time)
    elif (dns_trt_time > dns_trt_thresholds['warn']):
        return str(dns_trt_time)
    else:
        return str(dns_trt_time)
def metric_classifier(value, expected, error_percentage_as_decimal, warn_percentage_as_decimal=0.05):
    if (value < (expected - ( expected * error_percentage_as_decimal ) )):
        return str(value)
    
    if (value >= expected + (expected * error_percentage_as_decimal * 2) ):
        return str(value)

    if (value >= expected - (expected * warn_percentage_as_decimal) ):
        return str(value)
    
    return str(value)
    

class dbbox:
    dl = u'\u255a'
    ul = u'\u2554'
    dc = u'\u2569'
    uc = u'\u2566'
    lc = u'\u2560'
    u = u'\u2550'
    c = u'\u256c'
    l = u'\u2551'

P1 = "P1"
H1 = "H1"
H2 = "H2"
B1 = "B1"
B2 = "B2"
END_SECTION = "END_SECTION"


def vprint(text, style="B1"):
    if print_console == True:
        if (text == "END_SECTION"):
            print(dbbox.dl + (dbbox.u*20))
            print(" ")
        elif (style == "P1"):
            print(dbbox.ul + (dbbox.u*20))
            print(dbbox.l + pBold(text))
            print(dbbox.dl + (dbbox.u*20))
        elif (style == "H1"):
            print(dbbox.ul + (dbbox.u*20))
            print(dbbox.l + pBold(text))
            print(dbbox.lc + (dbbox.u*20))
        elif (style == "H2"):
            print(dbbox.lc + (dbbox.u*20))
            print(dbbox.l + pBold(text))
            print(dbbox.lc + (dbbox.u*20))
        elif (style == "B1"):
            print(dbbox.l + text)
        elif (style == "B2"):
            print(dbbox.l + " " + text)

    if (print_pdf == True):
        pass



def getpanstatus(webcontent, str_service):
    services_list = webcontent.xpath('//*[@data-component-id="' + str_service + '"]/span')
    if (len(services_list) == 4):
        service_status = (services_list[2].text).lstrip().rstrip()
    else:
        service_status = (services_list[1].text).lstrip().rstrip()
    return service_status

def parse_arguments():
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=PROGRAM_DESCRIPTION
            )
    parser.add_argument('--token', '-t', metavar='"MYTOKEN"', type=str, 
                    help='specify an authtoken to use for CloudGenix authentication')
    parser.add_argument('--authtokenfile', '-f', metavar='"MYTOKENFILE.TXT"', type=str, 
                    help='a file containing the authtoken')
    parser.add_argument('--site-name', '-s', metavar='SiteName', type=str, 
                    help='The site to run the site health check for', required=False)
    args = parser.parse_args()
    CLIARGS.update(vars(args)) ##ASSIGN ARGUMENTS to our DICT
def authenticate():
    #vprint("Authenticating",H1)
    user_email = None
    user_password = None
    """
    ##First attempt to use an AuthTOKEN if defined
    if CLIARGS['token']:                    #Check if AuthToken is in the CLI ARG
        CLOUDGENIX_AUTH_TOKEN = CLIARGS['token']
        vprint("Authenticating using Auth-Token in from CLI ARGS", B1)
    elif CLIARGS['authtokenfile']:          #Next: Check if an AuthToken file is used
        tokenfile = open(CLIARGS['authtokenfile'])
        CLOUDGENIX_AUTH_TOKEN = tokenfile.read().strip()
        vprint("Authenticating using Auth-token from file: " + pUnderline(CLIARGS['authtokenfile']), B1)
    elif "X_AUTH_TOKEN" in os.environ:              #Next: Check if an AuthToken is defined in the OS as X_AUTH_TOKEN
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('X_AUTH_TOKEN')
        vprint("Authenticating using environment variable X_AUTH_TOKEN", B1)
    elif "AUTH_TOKEN" in os.environ:                #Next: Check if an AuthToken is defined in the OS as AUTH_TOKEN
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
        vprint("Authenticating using environment variable AUTH_TOKEN", B1)
    else:                                           #Next: If we are not using an AUTH TOKEN, set it to NULL        
        CLOUDGENIX_AUTH_TOKEN = None
        vprint("Authenticating using interactive login", B1)"""
    ##ATTEMPT AUTHENTICATION
    if CLOUDGENIX_AUTH_TOKEN:
        cgx_session.interactive.use_token(CLOUDGENIX_AUTH_TOKEN)
        if cgx_session.tenant_id is None:
            vprint(pFail("ERROR") + ": AUTH_TOKEN login failure, please check token.", B1)
            sys.exit()
    else:
        while cgx_session.tenant_id is None:
            cgx_session.interactive.login(user_email, user_password)
            # clear after one failed login, force relogin.
            if not cgx_session.tenant_id:
                user_email = None
                user_password = None            
    #vprint(pPass("SUCCESS") + ": Authentication Complete", B1)
    #vprint(END_SECTION)

def verify(name):
    
    parse_arguments()
    authenticate()

    idname =  cloudgenix_idname.CloudGenixIDName(cgx_session)
    vpnpaths_id_to_name = idname.generate_anynets_map()
    

    #keyname_dict = cloudgenix_idname.generate_id_name_map(cgx_session, reverse=True)

    ####CODE GOES BELOW HERE#########
    resp = cgx_session.get.tenants()
    if resp.cgx_status:
        tenant_name = resp.cgx_content.get("name", None)
        #vprint("TENANT NAME: " + pUnderline(tenant_name), "H1")
        print("\n##################################################################\n")
        print("TENANT NAME: " + tenant_name)
        
        
    else:
        logout()
        vprint(pFail("ERROR") + ": API Call failure when enumerating TENANT Name! Exiting!", P1)
        print(resp.cgx_status)
        sys.exit((vars(resp)))

    site_count = 0
    search_site = name
    search_ratio = 0
    site_name = None
    site_id = None


    ###FIND the site in question
    resp = cgx_session.get.sites()
    if resp.cgx_status:
        site_list = resp.cgx_content.get("items", None)    #EVENT_LIST contains an list of all returned events
        for site in site_list:                            #Loop through each EVENT in the EVENT_LIST
            if search_site == site['name']:
                site_id = site['id']
                site_name = site['name']
                #search_ratio = check_ratio
                
    else:
        logout()
        vprint(pFail("ERROR") + "API Call failure when enumerating SITES in tenant! Exiting!", P1)
        sys.exit((jd(resp)))
    
    if site_id == None:
        print("ERROR" + "Site not found")
        return

    #vprint("Health Check for SITE: '" + pUnderline(pBold(site_name)) + "' SITE ID: " + pBold(site_id), B1)
    print("\n##################################################################\n")
    
    print("Health Check for SITE: " + site_name + " SITE ID: " + site_id)
    #vprint(END_SECTION)

    ###Check if elements are online
    site_elements = []
    element_count = 0
    resp = cgx_session.get.elements()
    if resp.cgx_status:
        
        #vprint("ION Status for site", H1)
        print("\n##################################################################\n")
        #print("ION Status for site")
        
        element_list = resp.cgx_content.get("items", None)    #EVENT_LIST contains an list of all returned events
        
        if (len(element_list) >= 0):
            for element in element_list:                            #Loop through each EVENT in the EVENT_LIST
                if (element['site_id'] == site_id):
                    element_count += 1
                    site_elements.append(element['id'])
                    if (element_count > 1):
                        print(dbbox.l)
                    #vprint("ION found NAME: " + pBold(str(element['name'])) + " ION ID: " + pBold(str(element['id'])), B1)
                    print("ION found NAME: " + str(element['name']) + " ION ID: " + str(element['id']))
                    if (element['connected'] == True):
                        #vprint("ION Status: " + pPass("CONNECTED"), B2)
                        print("ION Status: " + "CONNECTED")
                    else:
                        #vprint("ION Status: " + pFail("OFFLINE (!!!)"), B2)
                        print("ION Status: " + "OFFLINE (!!!)")
        if (element_count == 0):
            #vprint("ION Status: " + pBold("No IONS for site found"), B1)
            print("ION Status: " + "No IONS for site found")
        #vprint(END_SECTION)
    
    ################### ALARMS ###################
    ### Get last 5 ALARMS for last diff_hours hours
    
    dt_now = str(datetime.now().isoformat())
    dt_start = str((datetime.today() - timedelta(hours=diff_hours)).isoformat())
    dt_yesterday = str((datetime.today() - timedelta(hours=48)).isoformat())
    
    event_filter = '{"limit":{"count":5,"sort_on":"time","sort_order":"descending"},"view":{"summary":false},"severity":[],"query":{"site":["' + site_id + '"],"category":[],"code":[],"correlation_id":[],"type":["alarm"]}, "start_time": "' + dt_start + '", "end_time": "'+ dt_now + '"}'
    resp = cgx_session.post.events_query(event_filter)
    if resp.cgx_status:
        #vprint("Last 5 Alarms for site within the past "+ str(diff_hours) +" hours", H1)
        print("\n##################################################################\n")
        print("Last 5 Alarms for site within the past "+ str(diff_hours) +" hours")
        
        alarms_list = resp.cgx_content.get("items", None)
        if(len(alarms_list) == 0 ):
            #vprint("No Alarms found in the past " + str(diff_hours) + " hours",B1)
            print("No Alarms found in the past " + str(diff_hours) + " hours")
        else:
            for alarm in alarms_list:
                print("ALARM: " + str(alarm['code']))
                print("Acknowledged: " + str(alarm['cleared']))
                if (alarm['severity'] == "minor"):
                    print("Severity    : " + str(alarm['severity']))
                elif (alarm['severity'] == "major"):
                    print("Severity    : " + str(alarm['severity']))
                else:
                    print("Severity    : " + str(alarm['severity']))
                print("Timestamp   : " + str(alarm['time']))
    else:
        print("ERROR in SCRIPT. Could not get ALARMS")

    ### Get SUMMARY ALARMS  for last diff_hours hours
    alarm_summary_dict = {}
    event_filter = '{"limit":{"count":1000,"sort_on":"time","sort_order":"descending"},"view":{"summary":false},"severity":[],"query":{"site":["' + site_id + '"],"category":[],"code":[],"correlation_id":[],"type":["alarm"]}, "start_time": "' + dt_start + '", "end_time": "'+ dt_now + '"}'
    resp = cgx_session.post.events_query(event_filter)
    if resp.cgx_status:
        print("\n##################################################################\n")
        print("Alarm Summaries for the past " + str(diff_hours) + " hours")
        alarms_list = resp.cgx_content.get("items", None)
        if(len(alarms_list) > 0 ):
            for alarm in alarms_list:
               if(alarm['code'] in alarm_summary_dict.keys() ):
                   alarm_summary_dict[alarm['code']] += 1
               else:
                   alarm_summary_dict[alarm['code']] = 1
            for alarm_code in alarm_summary_dict.keys():
                print("CODE: " + str(alarm_code))
                print("TOTAL Count: " + str(alarm_summary_dict[alarm_code]))
        else:
            print("No Alarm summaries")
    else:
        print("ERROR in SCRIPT. Could not get ALARMS")
    #vprint(END_SECTION)

    ################### ALERTS ###################
    ### Get last 5 ALERTS for last diff_hours hours
    event_filter = '{"limit":{"count":5,"sort_on":"time","sort_order":"descending"},"view":{"summary":false},"severity":[],"query":{"site":["' + site_id + '"],"category":[],"code":[],"correlation_id":[],"type":["alert"]}, "start_time": "' + dt_start + '", "end_time": "'+ dt_now + '"}'
    resp = cgx_session.post.events_query(event_filter)
    if resp.cgx_status:
        print("\n##################################################################\n")
        print("Last 5 Alerts for site within the past "+ str(diff_hours) +" hours")
        
        alerts_list = resp.cgx_content.get("items", None)
        if(len(alerts_list) == 0 ):
            print("No Alerts found")
        else:
            for alert in alerts_list:
                print("ALERT CODE: " + str(alert['code']))
                if ( 'reason' in alert['info'].keys()):
                    print("REASON    : " + str(alert['info']['reason']))
                if ( 'process_name' in alert['info'].keys()):
                    print("PROCESS   : " + str(alert['info']['process_name']))
                if ( 'detail' in alert['info'].keys()):
                    print("DETAIL    : " + str(alert['info']['detail']))
                if (alert['severity'] == "minor"):
                    print("SEVERITY  : " + str(alert['severity']))
                elif (alert['severity'] == "major"):
                    print("SEVERITY  : " + (str(alert['severity'])))
                else:
                    print("SEVERITY  : " + (str(alert['severity'])))
                print("TIMESTAMP : " + str(alert['time']))
    else:
        print("ERROR in SCRIPT. Could not get Alerts")

    ### Get ALERTS summary for last diff_hours hours
    alert_summary_dict = {}
    event_filter = '{"limit":{"count":1000,"sort_on":"time","sort_order":"descending"},"view":{"summary":false},"severity":[],"query":{"site":["' + site_id + '"],"category":[],"code":[],"correlation_id":[],"type":["alert"]}, "start_time": "' + dt_start + '", "end_time": "'+ dt_now + '"}'
    resp = cgx_session.post.events_query(event_filter)
    if resp.cgx_status:
        print("\n##################################################################\n")
        print("Alert Summaries for the past " + str(diff_hours) + " hours")
        

        alerts_list = resp.cgx_content.get("items", None)
        if(len(alerts_list) > 0 ):
            for alert in alerts_list:
               if(alert['code'] in alert_summary_dict.keys() ):
                   alert_summary_dict[alert['code']] += 1
               else:
                   alert_summary_dict[alert['code']] = 1
            for alert_code in alert_summary_dict.keys():
                print("CODE: " + str(alert_code))
                print("TOTAL Count: " + str(alert_summary_dict[alert_code]))
        else:
            print("No Alarm summaries")
    else:
        print("ERROR in SCRIPT. Could not get Alerts")
    #vprint(END_SECTION)

    elements_id_to_name = idname.generate_elements_map()
    site_id_to_name = idname.generate_sites_map()
    wan_label_id_to_name = idname.generate_waninterfacelabels_map()
    wan_if_id_to_name = idname.generate_waninterfaces_map()
    
    wan_interfaces_resp = cgx_session.get.waninterfaces(site_id)
    wan_interfaces_list = wan_interfaces_resp.cgx_content.get("items")

    ### GET  LINKS status (VPN/PHYS)
    topology_filter = '{"type":"basenet","nodes":["' +  site_id + '"]}'
    resp = cgx_session.post.topology(topology_filter)
    if resp.cgx_status:
        topology_list = resp.cgx_content.get("links", None)
        print("\n##################################################################\n")
        print("VPN STATUS") 
        vpn_count = 0 
        for links in topology_list:

            if ((links['type'] == 'vpn') and links['source_site_name'] == site_name):
                vpn_count += 1
                #print(dbbox.l + format(vpnpaths_id_to_name.get(links['path_id'], links['path_id'])))
                print("VPN " + str(vpn_count) + "-> SITE:" + site_name + " [ION:" + elements_id_to_name[links['source_node_id']] + "]" + " ---> "+  wan_if_id_to_name[links['source_wan_if_id']] + ":" + links['source_wan_network'] 
                       + " " +  (dbbox.u*3) + (dbbox.c) + (dbbox.u*3) + " " + links['target_wan_network'] + ":" + wan_if_id_to_name[links['target_wan_if_id']] + " <--- [" +  elements_id_to_name[links['target_node_id']] + "] " + links['target_site_name'])
                if (links['status'] == "up"):
                    print("STATUS: " + "UP")
                else:
                    print("STATUS: " + "DOWN")
        if (vpn_count == 0):
            print("No SDWAN VPN links found at site")
        #vprint(END_SECTION)
        
         
        pcm_metrics_array_up = []  
        pcm_metrics_array_down = []  
        print("PHYSICAL LINK STATUS")
        stub_count = 0
        for links in topology_list:
            if ((links['type'] == 'internet-stub')):
                stub_count += 1
                if ('target_circuit_name' in links.keys()):
                    print("Physical LINK: " + str(links['network']) + ":" + str(links['target_circuit_name']))
                else:
                    print("Physical LINK: " + str(links['network']))                    
                if (links['status'] == "up"):
                    print("STATUS: " + "UP")
                elif (links['status'] == "init"):
                    print("STATUS: " + "INIT")
                else:
                    print("STATUS: " + "DOWN")
                
                print("\n##################################################################\n")
                ###PCM BANDWIDTH CAPACITY MEASUREMENTS
                pcm_request = '{"start_time":"'+ dt_start + 'Z","end_time":"' + dt_now + 'Z","interval":"5min","view":{"summary":false,"individual":"direction"},"filter":{"site":["' + site_id + '"],"path":["' + links['path_id'] + '"]},"metrics":[{"name":"PathCapacity","statistics":["average"],"unit":"Mbps"}]}'
                pcm_resp = cgx_session.post.metrics_monitor(pcm_request)
                pcm_metrics_array_up.clear()
                pcm_metrics_array_down.clear()
                measurements_up = 0
                measurements_down = 0
                z_count_down = 0
                z_count_up = 0
                if pcm_resp.cgx_status:
                    pcm_metric = pcm_resp.cgx_content.get("metrics", None)[0]['series']
                    if pcm_metric[0]['view']['direction'] == 'Ingress':
                        direction = "Download"
                    for series in pcm_metric:
                        if direction == "Download":                            
                            for datapoint in series['data'][0]['datapoints']:
                                if (datapoint['value'] == None):
                                    #pcm_metrics_array_down.append(0)
                                    z_count_down += 1
                                else:
                                    pcm_metrics_array_down.append(datapoint['value'])
                                    measurements_down += 1
                            direction = 'Upload'
                        else:
                            for datapoint in series['data'][0]['datapoints']:                                
                                if (datapoint['value'] == None):
                                    #pcm_metrics_array_up.append(0)
                                    z_count_up += 1
                                else:
                                    pcm_metrics_array_up.append(datapoint['value'])
                                    measurements_up += 1
                            direction = 'Download'

                    print("Configured Bandwidth/Throughput for the site")
                    
                    for wan_int in wan_interfaces_list:
                        if wan_int['id'] == links['path_id']:
                            upload = wan_int['link_bw_up']
                            download = wan_int['link_bw_down']
                            print("Maximum BW Download : " + str(wan_int['link_bw_down']))
                            print("Maximum BW Upload   : " + str(wan_int['link_bw_up']))
                    
                    error_percentage = 0.1
                    warn_percentage = 0.05
                    print("Measured Link Capacity (PCM) STATS for the last 24 hours")
                    #print("THRESHOLDS: "+ pFail("RED") + ">=" + (str(error_percentage*100)) + "% |  "+ "YELLOW"  + ">=" + (str(warn_percentage*100)) + "%  | "+ "GREEN" + "=Within " + (str(warn_percentage*100)) + "% | " + pExceptional("BLUE") + "="+ (str(error_percentage*100*2)) + "% Above expected")

                    print("Upload - Calculated from " + str(measurements_up) + " Measurements in the past 24 Hours in mbits")
                    if (len(pcm_metrics_array_up) == 0):
                        pcm_metrics_array_up.append(0)
                    if (len(pcm_metrics_array_down) == 0):
                        pcm_metrics_array_down.append(0)
                    
                    np_array = np.array(pcm_metrics_array_up)
                    
                    #vprint("Zeros:" + str(z_count_up), B1)
                    print("25th percentile      : " + metric_classifier( round(np.percentile(np_array,25),3),upload,error_percentage,warn_percentage))
                    print("50th Percentile(AVG) : " + metric_classifier( round(np.average(np_array),3),upload,error_percentage,warn_percentage))
                    print("75th percentile      : " + metric_classifier( round(np.percentile(np_array,75),3),upload,error_percentage,warn_percentage))
                    print("95th percentile      : " + metric_classifier( round(np.percentile(np_array,95),3),upload,error_percentage,warn_percentage))
                    print("Max Value            : " + metric_classifier( round(np.amax(np_array),3),upload,error_percentage,warn_percentage))
                    
                    print("Download - Calculated from " + str(measurements_up) + " Measurements in the past 24 Hours")
                    
                    np_array = np.array(pcm_metrics_array_down)
                    #vprint("Zeros:" + str(z_count_down), B1)
                    print("25th percentile      : " + metric_classifier( round(np.percentile(np_array,25),3),download,error_percentage,warn_percentage))
                    print("50th Percentile(AVG) : " + metric_classifier( round(np.average(np_array),3),download,error_percentage,warn_percentage))
                    print("75th percentile      : " + metric_classifier( round(np.percentile(np_array,75),3),download,error_percentage,warn_percentage))
                    print("95th percentile      : " + metric_classifier( round(np.percentile(np_array,95),3),download,error_percentage,warn_percentage))
                    print("Max Value            : " + metric_classifier( round(np.amax(np_array),3),download,error_percentage,warn_percentage))
                #vprint(END_SECTION)
                    

        if (stub_count == 0):
            print("No Physical links found at site")
            #vprint(END_SECTION)
        
        print("\n##################################################################\n")
        print("3RD PARTY LINK STATUS")
        service_link_count = 0
        for links in topology_list:
            if ((links['type'] == 'servicelink')):
                service_link_count += 1
                print("3RD PARTY LINK: " + str(links['sep_name']) + " VIA WAN " + pUnderline(str(links['wan_nw_name'])))
                if (links['status'] == "up"):
                    print("STATUS: " + "UP")
                else:
                    vprint("STATUS: " + "DOWN")
        if (service_link_count == 0):
            print("No 3rd party VPN tunnels found")
        #vprint(END_SECTION)
        
        
    #######DNS RESPONSE TIME:
    app_name_map = {}    
    app_name_map = idname.generate_appdefs_map(key_val="display_name", value_val="id")
    if ("dns" in app_name_map.keys()):
        dns_app_id = app_name_map['dns']   
        dns_request = '{"start_time":"' + dt_start + 'Z","end_time":"'+ dt_now + 'Z","interval":"5min","metrics":[{"name":"AppUDPTransactionResponseTime","statistics":["average"],"unit":"milliseconds"}],"view":{},"filter":{"site":["' + site_id + '"],"app":["' + dns_app_id + '"],"path_type":["DirectInternet","VPN","PrivateVPN","PrivateWAN","ServiceLink"]}}'
        dns_trt_array = []
        resp = cgx_session.post.metrics_monitor(dns_request)
        if resp.cgx_status:
            dns_metrics = resp.cgx_content.get("metrics", None)[0]['series'][0]
            for datapoint in dns_metrics['data'][0]['datapoints']:
                if (datapoint['value'] == None):
                    dns_trt_array.append(0)
                else:
                    dns_trt_array.append(datapoint['value'])
            
            
            print("\n##################################################################\n")
            print("DNS TRT STATS")
            print("Stats for past 24 hours")
            

            np_array = np.array(dns_trt_array)
            print("Min             : " + dns_trt_classifier( round(np.amin(np_array),2)))
            print("average         : " + dns_trt_classifier( round(np.average(np_array),2)))
            print("80th percentile : " + dns_trt_classifier( round(np.percentile(np_array,80),2)))
            print("95th percentile : " + dns_trt_classifier( round(np.percentile(np_array,95),2)))
            print("Max Value       : " + dns_trt_classifier( round(np.amax(np_array),2) ))

            ### Get stats from 48 hours ago
            dns_request = '{"start_time":"' + dt_yesterday + 'Z","end_time":"'+ dt_start + 'Z","interval":"5min","metrics":[{"name":"AppUDPTransactionResponseTime","statistics":["average"],"unit":"milliseconds"}],"view":{},"filter":{"site":["' + site_id + '"],"app":["' + dns_app_id + '"],"path_type":["DirectInternet","VPN","PrivateVPN","PrivateWAN","ServiceLink"]}}'
            dns_trt_array.clear()
            resp = cgx_session.post.metrics_monitor(dns_request)
            dns_metrics = resp.cgx_content.get("metrics", None)[0]['series'][0]
            for datapoint in dns_metrics['data'][0]['datapoints']:
                if (datapoint['value'] == None):
                    dns_trt_array.append(0)
                else:
                    dns_trt_array.append(datapoint['value'])

            print("Stats from Yesterday")
        
            np_array_yesterday = np.array(dns_trt_array)
            print("Min             : " + dns_trt_classifier( round(np.amin(np_array_yesterday),2)))
            print("average         : " + dns_trt_classifier( round(np.average(np_array_yesterday),2)))
            print("80th percentile : " + dns_trt_classifier( round(np.percentile(np_array_yesterday,80),2)))
            print("95th percentile : " + dns_trt_classifier( round(np.percentile(np_array_yesterday,95),2)))
            print("Max Value       : " + dns_trt_classifier( round(np.amax(np_array_yesterday),2)))
    else:
        print(pFail("ERROR: DNS APPLICATION NOT FOUND"))
    #vprint(END_SECTION)

    ###Get PAN STATUS
    pan_core_services_url = 'https://status.paloaltonetworks.com/'
    pan_health_request = requests.get(url = pan_core_services_url)
    pan_tree_data = html.fromstring(pan_health_request.content)
    print("\n##################################################################\n")
    print("Palo Alto Prisma Cloud STATUS from: " + pan_core_services_url)
    
    for service in pan_service_dict:
        service_status = getpanstatus(pan_tree_data, pan_service_dict[service] )
        if (service_status == "Operational"):
            print("SERVICE: " + service + "            STATUS: " + service_status)
        else:
            print("SERVICE: " + service + "            STATUS: " + service_status)
    #vprint(END_SECTION)


    ### Check MSFT Cloud Serivces status:
    ms_core_services_url = 'https://portal.office.com/api/servicestatus/index'
    print("\n##################################################################\n")
    
    print("Microsoft Cloud STATUS from: " + ms_core_services_url)
    
    ms_headers =  {'Content-type': 'application/json'}
    ms_health_request = requests.get(url = ms_core_services_url,  headers=ms_headers)
    ms_data = ms_health_request.json()

    if ('Services' in ms_data.keys()):
        for service in ms_data['Services']:
            if (service['IsUp']):
                print(service['Name'] + " STATUS: " + "GOOD")
            else:
                print(service['Name'] + " STATUS: " + "ISSUE DETECTED")
    #vprint(END_SECTION)

    ### Check Google Cloud Serivces status:
    google_core_services_url = 'https://www.google.com/appsstatus/json/en'
    
    print("\n##################################################################\n")
    print("Google Cloud STATUS from: " + google_core_services_url)
    
    google_headers =  {'Content-type': 'application/json'}
    google_health_request = requests.get(url = google_core_services_url,  headers=google_headers)
    google_data = json.loads(google_health_request.text.replace("dashboard.jsonp(","").replace("});","}"))

    google_service_list = {}
    for service in google_data['services']:
        google_service_list[service['id']] = service['name']

    google_issue_count = 0
    for messages in google_data['messages']:
        if (not(messages['resolved'])):
            google_issue_count += 1
            print(google_service_list[messages['service']] + " STATUS: " + "ISSUE DETECTED")
    if (google_issue_count == 0):
        print("No unresolved google cloud issues detected")
    print("\n##################################################################\n")
    #vprint(END_SECTION)


def logout():
    print("Logging out")
    cgx_session.get.logout()
if __name__ == "__main__":
    verify()
    logout()
