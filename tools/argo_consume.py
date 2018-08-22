#!/usr/bin/env python
from __future__ import print_function
import sys
import subprocess
import logging, os
import tempfile

secant_path = os.path.dirname(os.path.realpath(__file__)) + "/.."
sys.path.append(secant_path + "/include")

import py_functions
from argo_communicator import ArgoCommunicator

py_functions.setLogging()

def fail_report(msgId):
    data = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<SECANT>
  <VERSION>1.0</VERSION>
  <IMAGE_ID/>
  <DATE>%f</DATE>
  <OUTCOME>INTERNAL_FAILURE</OUTCOME>
  <OUTCOME_DESCRIPTION>Cloudkeeper failed to register image.</OUTCOME_DESCRIPTION>
  <MESSAGEID>%d</MESSAGEID>
</SECANT>""" % (time.time(), msgId)
    report_file = tempfile.NamedTemporaryFile(delete=False)
    report_file.write(data)
    report_file.close()
    return report_file.name

if __name__ == "__main__":
    argo = ArgoCommunicator()
    secant_conf_path = os.environ.get('SECANT_CONFIG_DIR', '/etc/secant') + '/' + 'secant.conf'
    url = py_functions.getSettingsFromBashConfFile(secant_conf_path, "IMAGE_LIST_URL")
    dir = py_functions.getSettingsFromBashConfFile(secant_conf_path, "IMAGE_LIST_DIR")
    state_dir = py_functions.getSettingsFromBashConfFile(secant_conf_path, "STATE_DIR")
    log_dir = py_functions.getSettingsFromBashConfFile(secant_conf_path, "LOG_DIR")

    registered_dir = state_dir + "/registered"
    if not os.path.isdir(registered_dir):
        os.mkdir(registered_dir, 755)

    images,msgids = argo.get_templates_for_assessment(dir)
    logging.info("Secant consumer: Obtained %d image list(s) for assessment" % (len(images)))

    cloudkeeper_log = open(log_dir + "/cloudkeeper.log", mode="a");

    for (img_list,msgId) in zip(images,msgids):
        #sudo -u cloudkeeper /opt/cloudkeeper/bin/cloudkeeper --image-lists=https://vmcaster.appdb.egi.eu/store/vappliance/demo.va.public/image.list --debug
        #img_list = "https://vmcaster.appdb.egi.eu/store/vappliance/demo.va.public/image.list"
        logging.debug("Secant consumer: Trying to register image list %s" % (img_list))
        img_url = "%s/%s" % (url, img_list)
        cmd = (["/opt/cloudkeeper/bin/cloudkeeper", "--image-lists=" + img_url, "--debug"])
        try:
            subprocess.check_call(cmd, stdout=cloudkeeper_log, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            report=fail_report(msgId)
            try:
                argo.post_assessment_results("", msgId, report, "")
            except Exception:
                logging.error("Failed to send fail report.")
            finally:
                os.remove(report)
            logging.error("Secant consumer: Registering image list %s failed: %s" % (img_list, e.output))
            print("Failed to register image %s, check the log." % img_list, file=sys.stderr)
            continue
        reg_list = tempfile.NamedTemporaryFile(prefix='image_list_', delete=False, dir=registered_dir)
        os.rename("%s/%s" % (dir, img_list), reg_list.name)
        logging.debug("Secant consumer: Image list %s has been registered as %s" % (img_list, os.path.basename(reg_list.name)))

    cloudkeeper_log.close()
