import base64
import logging
import sys
from threading import Thread
from time import sleep

import clr  # for converting bytes to base64
from fastapi import FastAPI, HTTPException
from System import Array

from pyzkfp import ZKFP2

sys.dont_write_bytecode = True  # don't create __pycache__

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class FingerprintScanner:
    def __init__(self):
        self.logger = logging.getLogger("fps")
        fh = logging.FileHandler("logs.log")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        self.logger.addHandler(fh)

        self.templates = []

        self.initialize_zkfp2()

        self.capture = None
        self.fid = 1

        self.keep_alive = True

        self.api_response = None

    def initialize_zkfp2(self):
        try:
            # Clean up existing instance if it exists
            if hasattr(self, 'zkfp2') and self.zkfp2:
                try:
                    self.zkfp2.Terminate()
                except Exception:
                    pass

            self.zkfp2 = ZKFP2()
            self.zkfp2.Init()
            device_count = self.zkfp2.GetDeviceCount()
            self.logger.info(f"{device_count} Devices found. Connecting to the first device.")

            if device_count == 0:
                raise Exception("No fingerprint devices found. Please connect a device and try again.")

            self.zkfp2.OpenDevice(0)
            self.zkfp2.Light("green")
        except Exception as e:
            self.logger.error(f"Failed to initialize fingerprint device: {e}")
            raise

    def cleanup(self):
        """Clean up device resources"""
        try:
            if hasattr(self, 'zkfp2') and self.zkfp2:
                self.zkfp2.CloseDevice()
                self.zkfp2.Terminate()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def capture_handler(self):
        try:
            tmp, img = self.capture
            fid, score = self.zkfp2.DBIdentify(tmp)

            try:
                print("==================================")
                print("Vamos a tratar de mostrar la imagen")
                self.zkfp2.show_image(img)
                print("==================================")
            except Exception:
                print("Advertencia: No se pudo mostrar la imagen")

            if fid:
                self.logger.info(f"successfully identified the user: {fid}, Score: {score}")
                self.zkfp2.Light("green")
                self.capture = None
                return


            if len(self.templates) < 3:
                if (
                    not self.templates or self.zkfp2.DBMatch(self.templates[-1], tmp) > 0
                ):  # check if the finger is the same
                    self.zkfp2.Light("green")
                    self.templates.append(tmp)

                    message = f"Finger {len(self.templates)} registered successfully! " + (
                        f"{3-len(self.templates)} presses left." if 3 - len(self.templates) > 0 else ""
                    )
                    self.logger.info(message)

                    try:
                        print("==================================")
                        print("Vamos a tratar de convertir la imagen a base64")
                        blob_image = self.zkfp2.Blob2Base64String(img) # convert the image to base64 string
                    except Exception:
                        print("Advertencia: No se pudo convertir la imagen a base64")

                    if len(self.templates) == 3:
                        regTemp, regTempLen = self.zkfp2.DBMerge(*self.templates)
                        #self.zkfp2.DBAdd(self.fid, regTemp)

                        # Convert bytes to base64 for JSON serialization
                        #template_base64 = bytes(regTemp)
                        #image_base64 = base64.b64encode(img).decode('utf-8') if isinstance(img, bytes) else img
                        print("Iniciando logs de pruebas")
                        print("Probaremos a convertir regTemp a base64 usando varias tecnicas")
                        try:
                            print("==================================")
                            print(bytes(regTemp).decode('utf-8'))
                        except Exception:
                            print("Advertencia: No se pudo convertir regTemp a string mediante bytes(regTemp).decode('utf-8')")

                        try:
                            print("==================================")
                            print(clr.convert_to_base64(regTemp))
                        except Exception:
                            print("Advertencia: No se pudo convertir regTemp a base64 mediante clr.convert_to_base64(regTemp)")

                        try:
                            print("==================================")
                            print(Array.ConvertAll[byte, byte](regTemp, lambda x: x))
                        except Exception:
                            print("Advertencia: No se pudo convertir regTemp con Array.ConvertAll[byte, byte](regTemp, lambda x: x)")

                        try:
                            print("==================================")
                            print(self.zkfp2.Blob2Base64String(regTemp))
                        except Exception:
                            print("Advertencia: No se pudo convertir regTemp con self.zkfp2.Blob2Base64String(regTemp)")
                        print("Finalizando logs de pruebas")

                        self.api_response = {
                            "array_length": regTempLen,
                            "template_raw": "PROBANDO",
                            "image_raw": blob_image
                        }
                        self.templates.clear()
                        self.fid += 1
                else:
                    self.zkfp2.Light("red", 1)
                    self.logger.warning("Different finger. Please enter the original finger!")

        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
            self.zkfp2.Terminate()
            exit(0)

        # release the capture
        self.capture = None

    def _capture_handler(self):
        try:
            self.capture_handler()
        except Exception as e:
            self.logger.error(e)
            self.capture = None

    def listenToFingerprints(self):
        try:
            while self.keep_alive:
                try:
                    capture = self.zkfp2.AcquireFingerprint()
                    if capture and not self.capture:
                        self.capture = capture
                        Thread(target=self._capture_handler, daemon=True).start()
                        if self.api_response:
                            template_base64 = base64.b64encode(capture[0]).decode('utf-8') if isinstance(capture[0], bytes) else capture[0]
                            self.api_response["template_raw"] = template_base64
                            self.capture = None
                            # Don't terminate here - let the calling function handle cleanup
                            return self.api_response
                except Exception as e:
                    self.logger.error(f"Error during fingerprint acquisition: {e}")
                    # If device handle is invalid, try to reinitialize
                    if "Invalid Handle" in str(e) or "DeviceNotStartedError" in str(e):
                        self.logger.info("Device handle invalid, attempting to reinitialize...")
                        try:
                            self.zkfp2.CloseDevice()
                        except Exception:
                            pass
                        self.initialize_zkfp2()
                        continue
                    else:
                        raise
                sleep(0.1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
            raise HTTPException(status_code=500, detail="Fingerprint capture failed")


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
    fingerprint_scanner = None
    try:
        fingerprint_scanner = FingerprintScanner()
        return fingerprint_scanner.listenToFingerprints()
    except Exception as e:
        logger.error(f"Fingerprint capture failed: {e}")
        raise HTTPException(status_code=500, detail=f"Fingerprint capture failed: {str(e)}")