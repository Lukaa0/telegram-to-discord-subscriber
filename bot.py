import asyncio
from io import BytesIO
import re
import disnake
from tinydb import TinyDB, Query, where
from disnake.ext import commands
from telethon import TelegramClient, events
from PIL import Image

db = TinyDB("db.json")
query = Query()

discord_bot = commands.Bot(
    command_prefix="$", sync_permissions=True, sync_commands=True
)
# API values, use .env in production or something more appropriate 
app_id = 0
app_hash = ''
client = TelegramClient("session", app_id, app_hash) 

def hex_to_rgb(hex_string):
    r_hex = hex_string[1:3]
    g_hex = hex_string[3:5]
    b_hex = hex_string[5:7]
    return int(r_hex, 16), int(g_hex, 16), int(b_hex, 16)


@client.on(events.NewMessage())
async def newMessageListener(event):
    linked_telegram = [r for r in db.table("linked_channels")]
    for linked_item in linked_telegram:
        if event.message.chat_id == linked_item["telegram_channel"]:
            try:
                message_obj = discord_bot.get_partial_messageable(
                    linked_item["discord_channel"]
                )
                image = None
                if event.photo:
                    image = await event.download_media("temp.png")
                await get_send_embed(
                    message_obj,
                    linked_item["role"],
                    event.text,
                    linked_item["telegram_channel_title"],
                    image,
                )
            except disnake.errors.NotFound:
                db.table("linked_channels").remove(where('discord_channel') == linked_item['discord_channel'])

@discord_bot.slash_command(description="disconnect")
async def disconnect(
    inter: disnake.ApplicationCommandInteraction,
    channel_id: str = None ,
):
    await inter.response.defer()
    try:
        channel : int
        if channel_id == None:
            channel = inter.channel_id
        else:
            channel = int(channel_id)
        channel_table = db.table("linked_channels")
        channel_table.remove(where('discord_channel') == channel)
        await inter.edit_original_message(content= "Deleted successfully")
    except Exception as ex:
        print(ex)
        await inter.edit_original_message(content= "Could not find channel. Verify that ID is correct")


async def get_send_embed(message, role, content, title, image_file=None):
    settings = [r["color"] for r in db.table("embed_settings")]
    color = settings[0]
    embed = disnake.Embed(title=title, color=color, description=content)
    file = None
    role_content = "" if role == 0 or role == None else role
    if image_file != None:
        with Image.open(image_file) as image:
            with BytesIO() as image_binary:
                image.save(image_binary, "PNG")
                image_binary.seek(0)
                file = disnake.File(fp=image_binary, filename="temp.png")
                embed = embed.set_image("attachment://temp.png")

    if file != None:
        await message.send(content=role_content, file=file, embed=embed)
    else:
        await message.send(content=role_content, embed=embed)


async def autocomplete_channels(
    inter: disnake.ApplicationCommandInteraction, user_input: str
):
    telegram_channels = [
        r["telegram_channel_name"] for r in db.table("telegram_channel")
    ]
    items = [channels for channels in telegram_channels if channels.lower().startswith(user_input.lower())]
    return items[:24]


def replace_all(pattern, repl, string) -> str:
   occurences = re.findall(pattern, string, re.IGNORECASE)
   for occurence in occurences:
       string = string.replace(occurence, repl)
       return string

async def set_all_channels():
    telegram_channel = db.table("telegram_channel")
    async for dialog in client.iter_dialogs():
        title = dialog.name
        title = title.rstrip()
        telegram_channel.upsert(
            {"telegram_channel_name": title, "telegram_channel_id": dialog.id},
            query.telegram_channel_id == dialog.id,
        )


@discord_bot.slash_command(
    description="Set embed color"
)
async def setcolor(inter:disnake.ApplicationCommandInteraction, color: str):
    await inter.response.defer()
    if inter.author.id != 313411599060959243 and inter.author.id != 632141792426459138:
        await inter.edit_original_message(content="You can't do that")
        return
    rgb = hex_to_rgb(color)
    color_obj = disnake.Colour.from_rgb(rgb[0], rgb[1], rgb[2])
    embed_settings = db.table("embed_settings")
    embed_settings.upsert({"color": color_obj.value}, query.color != "")
    await inter.edit_original_message(content="Color has been set")


@discord_bot.slash_command(description="connect")
async def connect(
    inter,
    discord_channel_name: disnake.TextChannel,
    telegram_name: str = commands.Param(autocomplete=autocomplete_channels),
    role: disnake.Role = None,
):
    await inter.response.defer()
    if inter.author.id != 313411599060959243 and inter.author.id != 632141792426459138:
        await inter.edit_original_message(content="You can't do that")
        return
    telegram_channels = [
        r["telegram_channel_name"] for r in db.table("telegram_channel")
    ]
    discord_channel_id = discord_channel_name.id
    role_id = 0
    if role != None:
        role_id = role.mention
    if telegram_name in telegram_channels:
        t_channel = db.table("telegram_channel")
        t_obj = t_channel.get(query.telegram_channel_name == telegram_name)
        link = db.table("linked_channels")
        link.upsert(
            {
                "telegram_channel": t_obj["telegram_channel_id"],
                "discord_channel": discord_channel_id,
                "role": role_id,
                "telegram_channel_title": telegram_name,
            },
            query.discord_channel == discord_channel_id,
        )
    await inter.edit_original_message(content="Channel has been linked")

@discord_bot.slash_command(description="update")
async def update(
    inter,
):
    await inter.response.defer()
    if inter.author.id != 313411599060959243 and inter.author.id != 632141792426459138:
        await inter.edit_original_message(content="You can't do that")
        return
    await set_all_channels()
    await inter.edit_original_message(content = "Initialization complete")


with client:
    loop = asyncio.get_event_loop()
    loop.create_task(
        discord_bot.run("OTk4NTY5NDcxODM5MDYwMDM4.GE8haG.dsLaI1prSxo4b2IUcDX0G-xb65JcXyBBRQi1U4")
    )
    loop.create_task(client.run_until_disconnected())
    print("Running service")
    loop.run_forever()
