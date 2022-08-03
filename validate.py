#!/usr/bin/env python

import os
import re
import subprocess
import yum
import json
import ConfigParser
import pdb  #pdb.settrace()
from requests import Session

RHSM_CONFIG='/etc/rhsm/rhsm.conf'
RHSM_CERT='/etc/pki/consumer/cert.pem'
RHSM_KEY='/etc/pki/consumer/key.pem'
TEMP_CERT='/var/tmp/reg_cert.pem'
COMMON_NAME=''
SATELLITE = ''
COMPLIANCE = {}

session = Session()
session.verify = True
session.cert = (RHSM_CERT, RHSM_KEY)

def get_rhsm_hostname():
    #Check if host is configured to Satellite
    cfg = ConfigParser.ConfigParser()
    cfg.read(RHSM_CONFIG)
    global SATELLITE
    SATELLITE = cfg.get('server', 'hostname')
    if SATELLITE == 'subscription.rhsm.redhat.com':
        print('Client is configured for the Red Hat Customer Portal')
        exit (1)

def check_reg_cert():
    # Check for /etc/pki/consumer/{cert,key}.pem
    if os.path.exists('/etc/pki/consumer/cert.pem') and os.path.exists('/etc/pki/consumer/key.pem'):
        return True
    else:
        return False

def check_sub_cert():
    #Check for any subscriptions
    if len(os.listdir('/etc/pki/entitlement/')):
        return True
    else:
        return False

def read_registration_cert():
    # Grab the CN from the /etc/pki/consumer/cert.pem
    if check_reg_cert():
        cert = subprocess.check_output(['rct', 'cat-cert', RHSM_CERT])
        for line in cert.splitlines():
            if re.search('CN:', line) and re.search('........-....', line):
                COMMON_NAME = line.strip()[4:42]
                return COMMON_NAME
    else:
        return COMMON_NAME

def make_call(endpoint):
    # Take endpoint and make a call to the Satellite
    call = session.get('https://' + SATELLITE + endpoint).json()
    return call

def get_complinace_output():
    # GET /rhsm/consumers/<CN>/compliance
    endpoint = '/rhsm/consumers/' + read_registration_cert() +'/compliance'
    global COMPLIANCE
    COMPLIANCE = make_call(endpoint)

def get_compliance_deleted():
    # Get compliance deleted message
    return COMPLIANCE.get('deleteId')

def get_compliance_status():
    # Get compliance status
    return COMPLIANCE.get("status")

def get_compliance_compliant():
    # Get compliance state
    return COMPLIANCE.get('compliant')

def get_compliance_nonCompliant():
    # Get non-compliant product id's
    return COMPLIANCE.get('nonCompliantProducts')

def get_compliance_partiallyCompliant():
    # Get partially compliant product id's
    return COMPLIANCE.get('partiallyCompliantProducts')

def get_compliance_reasons():
    # Get the message for any reason
#   COMPLIANCE.get('reasons')[0].get('message'
    reasons = COMPLIANCE.get('reasons')
    return reasons[0].get('message')


def main():
    # Get needed inforamtion
    get_rhsm_hostname()
    if not check_reg_cert():
        print('The /etc/pki/consumer/cert.pem file is not found')
        print('Is this system registered?')
        exit (1)
    elif check_reg_cert():
        # Get compliance information
        get_complinace_output()
        if get_compliance_deleted():
            print('Host with ID: ' + COMPLIANCE.get('deleteId') + ' has been deleted')
            print('Run subscription-manager refresh to regenerate certificates locally')
            exit (1)
        else:
            if get_compliance_status() == "partial":
                print('Registration Status:  Partial')
                print('Reason:  ' + get_compliance_reasons())
                print('Compliant:  ' + str(get_compliance_compliant()))
                if get_compliance_partiallyCompliant():
                    print('Partially Compliant Product IDs:  ' + get_compliance_partiallyCompliant())
                if get_compliance_nonCompliant():
                    print('Non-Compliant Product IDs:  ' + get_compliance_nonCompliant())
                exit (1)
            elif get_compliance_status() == 'invalid':
                print('Registration Status:  Unentitled')
                print('Reason:  ' + get_compliance_reasons())
                print('Compliant:  ' + str(get_compliance_compliant()))
                if get_compliance_partiallyCompliant():
                    print('Partially Compliant Product IDs:  ')
                    for id  in range(len(get_compliance_partiallyCompliant())):
                        print(get_compliance_partiallyCompliant()[id])
                if get_compliance_nonCompliant():
                    print('Non-Compliant Product IDs:  ')
                    for id in range(len(get_compliance_nonCompliant())):
                        print(get_compliance_nonCompliant()[id])
                exit (1)
            elif get_compliance_status() == 'valid':
                print('Registration Status:  Entitled')
                exit (0)
            elif get_compliance_status() == 'disabled':
                print('Relaxed Enforcement Enabled, no subscription needed')
                exit (0)


#if __name__ == '__main__':
main()