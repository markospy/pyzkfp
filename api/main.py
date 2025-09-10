import base64
import logging
from time import sleep

from fastapi import FastAPI, HTTPException

from pyzkfp import ZKFP2

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("fps")


@app.get("/fingerprint")
def fingerprint():
    """
    Endpoint that listens for fingerprint capture and returns the captured data.
    This endpoint will wait until a fingerprint is successfully captured.
    """
    zkfp2 = ZKFP2()

    try:
        # Initialize the device
        zkfp2.Init()
        device_count = zkfp2.GetDeviceCount()
        logger.info(f"{device_count} Devices found. Connecting to the first device.")

        if device_count == 0:
            raise HTTPException(status_code=500, detail="No fingerprint devices found")

        zkfp2.OpenDevice(0)
        zkfp2.Light("green")

        # Listen for fingerprint capture
        logger.info("Waiting for fingerprint capture...")
        while True:
            capture = zkfp2.AcquireFingerprint()
            if capture:
                logger.info("Fingerprint captured successfully")
                zkfp2.Light("green")

                # Convert template to base64 for easier handling
                template_base64 = base64.b64encode(capture[0]).decode("utf-8")
                image_base64 = base64.b64encode(capture[1]).decode("utf-8")

                fingerprint_data = {
                    "template": template_base64,
                    "image": image_base64,
                    "template_raw": capture[0],
                    "image_raw": capture[1]
                }

                zkfp2.Terminate()
                return fingerprint_data

            sleep(0.1)  # Small delay to prevent excessive CPU usage

    except Exception as e:
        logger.error(f"Error during fingerprint capture: {str(e)}")
        try:
            zkfp2.Terminate()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Fingerprint capture failed: {str(e)}")