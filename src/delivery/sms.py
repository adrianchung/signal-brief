from twilio.rest import Client

SMS_LIMIT = 1600
PREFIX = "HN Signal Brief\n"


class SMSDeliverer:
    def __init__(self, account_sid: str, auth_token: str, from_number: str, to_number: str) -> None:
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
        self.to_number = to_number

    def send(self, brief: str) -> None:
        body = PREFIX + brief
        if len(body) > SMS_LIMIT:
            body = body[: SMS_LIMIT - 3] + "..."
        self.client.messages.create(
            body=body,
            from_=self.from_number,
            to=self.to_number,
        )
