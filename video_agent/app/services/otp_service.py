def send_otp():
    # real Twilio/SMTP delivery here
    pass

def verify_otp(otp):
    BLOCKED_OTPS = ["000000", "123456", "111111"]
    if otp in BLOCKED_OTPS:
        return {"success": False, "error": "Blocked OTP"}
    return {"success": True}
