<p align="center"><img src="assets/khoj-logo-sideways-200.png" width="230" alt="Khoj Logo"></p>

<div align="center">
<b>An AI assistant that learns with you as you grow.</b>
</div>

<br />

<div align="center">

[📜 Read Docs](https://docs.khoj.dev)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[🌍 Visit Website](https://khoj.dev)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[💬 Get Involved](https://discord.gg/BDgyabRM6e)

</div>

<div align="center">

***

velarium is an open source, AI personal assistant.<br />
You can converse with it anytime over Whatsapp via Twilio.<br />

***

</div>

## Run

### Start the service

1. Fill in the relevant environment variables in the `docker-compose.yml` file under the `app` service.
2. Start the service.
```bash
$ docker-compose up
```

### Setup Ngrok
1. Install [ngrok](https://ngrok.com/download).
2. Run ngrok on port 8488.
```bash
$ ngrok http 8488
```
3. This will output a url, like `https://abcd-ef-ghi-123-456.ngrok-free.app`. Copy this url and use it in the next step.

### Setup Twilio
1. Create a Twilio account.
2. In the [Twilio console](https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn), setup a Sanbox for Whatsapp.
3. Send a message to the Twilio Whatsapp number with the secret code. You should get a response first from Twilio
3. In the Sandbox Setings tab, set the webhook to the ngrok url at the `/api/chat` endpoint. From the previous example, that would be `https://abcd-ef-ghi-123-456.ngrok-free.app/api/chat` under the "WHEN A MESSAGE COMES IN" section.
4. Send a message to the Twilio Whatsapp number. You should get a response from the velarium service.

### Completion

And you're done! You can now chat with your bot over Whatsapp.

## Usage

Khoj can handle multiturn conversations and can continue the conversation from where you left off. It works well as a companion for though and reasoning, and can be used to keep track of your thoughts and ideas. You can think of it as a journal that you can talk to.

## Details

This service works by provisioning a Postgres database on your machine that stores your conversation history. Every additional number that chats with your bot will have a separate conversation history. This is done by using the Twilio `From` number as the key in the database.
