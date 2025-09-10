from fastapi import FastAPI

from pyzkfp import ZKFP2

app = FastAPI()


@app.get("/fingerprint")
def fingerprint():
    zkfp2 = ZKFP2()
    zkfp2.Init()
    zkfp2.OpenDevice(0)
    capture = zkfp2.AcquireFingerprint()
    zkfp2.Terminate()
    fingerprint = {"image": capture[1], "template": capture[0]}
    return fingerprint