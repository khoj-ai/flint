<p align="center"><img src="assets/khoj-logo-sideways-500.png" width="250" alt="Khoj Logo"></p>

<div align="center">
<b>An open, personal AI that grows with you.</b>
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

Flint makes Khoj, your personal AI, accessible over Whatsapp.<br />
So you can converse with it easily, on your phone or computer.<br />

***

</div>

## ⭐️ Chat with Khoj on WhatsApp

If you want to start chatting with our hosted Khoj right away, you have two options:

1. 🪧 Use the QR code
    - Scan the QR code below using your phone's camera.
[![QR Code](assets/khoj-qr-code.png)](https://wa.me/18488004242)
2. 📞 Directly use the phone number
    - Add the number [+1 (848) 800-4242](https://wa.me/18488004242) to your contacts and send a message to it on WhatsApp.

## Run it yourself

You can get setup with your own instance of Khoj via WhatsApp in a few simple steps.

### Start the service

#### Docker setup

1. Fill in the relevant environment variables in the `docker-compose.yml` file under the `app` service.
2. Start the service.
```bash
$ docker-compose up
```

##### Run migrations

In order to setup the database, you need to run the migrations. This needs to be done before you can start using the service, and anytime a new migration is added.

1. SSH into the docker container. You can get the name of the container by running `docker container ls`.
```bash
$ docker exec -it khoj_app_1 bash
```

2. Run the migrations.
```bash
$ python3 src/flint/manage.py migrate
```

#### Test that it's working

1. Go to `localhost:8488/docs` in your browser. You should see the Swagger UI.
2. Click on the `/dev/chat` endpoint.
3. Click on the "Try it out" button.
4. Enter any prompt in the `Body` field and click on the "Execute" button. You should get a response from the flint service.

If this didn't work, you might need to debug what's wrong.

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
4. Send a message to the Twilio Whatsapp number. You should get a response from the flint service.

### Completion

And you're done! You can now chat with your bot over Whatsapp. When you're done finalizing your bot, make sure to flip the `DEBUG` flag in the `docker-compose.yml` file to `False` or remove it altogether.

## Usage

Khoj can handle multiturn conversations and can continue the conversation from where you left off. It works well as a companion for though and reasoning, and can be used to keep track of your thoughts and ideas. You can think of it as a journal that you can talk to.

## Details

This service works by provisioning a Postgres database on your machine that stores your conversation history. Every additional number that chats with your bot will have a separate conversation history. This is done by using the Twilio `From` number as the key in the database.
