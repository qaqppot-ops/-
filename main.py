import discord
from discord import app_commands
from discord.ext import commands
import datetime
import os
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ---------- Railway Volume 路徑設定 ----------
# 優先使用 Railway 的 VOLUME_PATH 環境變數，若無則使用預設路徑
VOLUME_PATH = os.getenv("VOLUME_PATH", "/app/data")
CATEGORIES_FILE = os.path.join(VOLUME_PATH, "categories.json")

# 確保 Volume 目錄存在
os.makedirs(VOLUME_PATH, exist_ok=True)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- 分類資料儲存（JSON） ----------
def load_categories():
    """讀取所有伺服器的分類設定"""
    if os.path.exists(CATEGORIES_FILE):
        with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_categories(data):
    """儲存分類設定"""
    with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_guild_categories(guild_id):
    """取得特定伺服器的分類列表"""
    data = load_categories()
    guild_id_str = str(guild_id)
    if guild_id_str not in data:
        data[guild_id_str] = {}  # 預設為空
        save_categories(data)
    return data[guild_id_str]

def set_guild_categories(guild_id, categories_dict):
    """設定特定伺服器的分類"""
    data = load_categories()
    data[str(guild_id)] = categories_dict
    save_categories(data)

# 暫存開單紀錄（正式可用資料庫）
ticket_logs = {}

# ---------- 啟動事件 ----------
@bot.event
async def on_ready():
    print(f"✅ {bot.user} 已上線！")
    print(f"📁 Volume 路徑：{VOLUME_PATH}")
    print(f"📄 分類檔案：{CATEGORIES_FILE}")
    
    # 檢查 Volume 是否可寫入
    try:
        test_file = os.path.join(VOLUME_PATH, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        print("✅ Volume 讀寫正常")
    except Exception as e:
        print(f"⚠️ Volume 讀寫異常：{e}")
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ 已同步 {len(synced)} 個斜線指令")
    except Exception as e:
        print(f"⚠️ 同步指令失敗：{e}")

# ========== 管理指令區 ==========

# ---------- 新增分類 ----------
@bot.tree.command(name="ticket_add", description="新增一個開單分類（管理員）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    name="分類名稱",
    emoji="表情符號（可選，例如 📦）"
)
async def ticket_add(interaction: discord.Interaction, name: str, emoji: str = "📌"):
    guild_id = interaction.guild.id
    categories = get_guild_categories(guild_id)
    
    if name in categories:
        embed = discord.Embed(
            title="⚠️ 分類已存在",
            description=f"分類「{name}」已經存在！",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    categories[name] = emoji
    set_guild_categories(guild_id, categories)
    
    embed = discord.Embed(
        title="✅ 分類已新增",
        description=f"已新增分類：{emoji} **{name}**",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"目前共 {len(categories)} 個分類")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------- 刪除分類 ----------
@bot.tree.command(name="ticket_remove", description="刪除一個開單分類（管理員）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(name="要刪除的分類名稱")
async def ticket_remove(interaction: discord.Interaction, name: str):
    guild_id = interaction.guild.id
    categories = get_guild_categories(guild_id)
    
    if name not in categories:
        embed = discord.Embed(
            title="⚠️ 找不到分類",
            description=f"找不到分類「{name}」",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    emoji = categories.pop(name)
    set_guild_categories(guild_id, categories)
    
    embed = discord.Embed(
        title="🗑️ 分類已刪除",
        description=f"已移除分類：{emoji} **{name}**",
        color=discord.Color.orange()
    )
    embed.set_footer(text=f"剩餘 {len(categories)} 個分類")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------- 查看所有分類 ----------
@bot.tree.command(name="ticket_list", description="查看目前所有開單分類")
async def ticket_list(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    categories = get_guild_categories(guild_id)
    
    if not categories:
        embed = discord.Embed(
            title="📭 目前沒有分類",
            description="請使用 `/ticket_add` 新增分類",
            color=discord.Color.gray()
        )
    else:
        embed = discord.Embed(
            title="📂 開單分類列表",
            description=f"共 {len(categories)} 個分類",
            color=discord.Color.blue()
        )
        for name, emoji in categories.items():
            embed.add_field(
                name=f"{emoji} {name}",
                value="‎",  # 零寬空格，保持排版
                inline=False
            )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------- 建立開單面板（動態讀取分類） ----------
@bot.tree.command(name="ticket_panel", description="建立開單分類選擇面板（管理員專用）")
@app_commands.default_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    categories = get_guild_categories(guild_id)
    
    if not categories:
        embed = discord.Embed(
            title="⚠️ 沒有任何分類",
            description="請先使用 `/ticket_add` 新增分類！",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🎫 開單系統",
        description="請從下方選單選擇您要開單的類別，系統將為您建立專屬頻道。",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="📋 可用分類",
        value="\n".join([f"{emoji} {name}" for name, emoji in categories.items()]),
        inline=False
    )
    embed.set_footer(text="系統將自動記錄開單資訊")

    # 動態建立下拉選單
    select = discord.ui.Select(
        placeholder="請選擇開單分類...",
        options=[
            discord.SelectOption(label=name, value=name, emoji=emoji)
            for name, emoji in categories.items()
        ]
    )

    async def select_callback(interaction: discord.Interaction):
        category_name = interaction.data["values"][0]
        guild = interaction.guild
        member = interaction.user

        # 建立開單分類（頻道群組）
        category = discord.utils.get(guild.categories, name="📩 票單")
        if not category:
            category = await guild.create_category("📩 票單")

        # 建立票單頻道
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        channel_name = f"ticket-{member.name}-{timestamp}"
        
        # 確保頻道名稱不超過 100 字元
        if len(channel_name) > 100:
            channel_name = channel_name[:97] + "..."
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites
        )

        # 記錄開單資訊
        ticket_logs[channel.id] = {
            "user": member.id,
            "category": category_name,
            "created_at": datetime.datetime.now().isoformat()
        }

        # 發送開單資訊（美化 Embed）
        embed_ticket = discord.Embed(
            title="🎫 票單已開啟",
            description=f"感謝您使用開單系統，以下是您的票單資訊：",
            color=discord.Color.green()
        )
        embed_ticket.add_field(name="👤 開單人", value=member.mention, inline=True)
        embed_ticket.add_field(name="📂 分類", value=category_name, inline=True)
        embed_ticket.add_field(name="🕒 時間", value=f"<t:{int(datetime.datetime.now().timestamp())}:F>", inline=False)
        embed_ticket.add_field(name="📌 頻道", value=channel.mention, inline=False)
        embed_ticket.set_footer(text="請等待工作人員回覆")

        # 關閉按鈕
        close_button = discord.ui.Button(label="🔒 關閉票單", style=discord.ButtonStyle.danger)

        async def close_callback(interaction: discord.Interaction):
            if interaction.channel.id == channel.id:
                embed_close = discord.Embed(
                    title="⏳ 票單關閉中",
                    description="此票單將在 5 秒後關閉...",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed_close)
                await channel.delete()
            else:
                embed_error = discord.Embed(
                    title="❌ 錯誤",
                    description="此按鈕僅能在票單頻道使用",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed_error, ephemeral=True)

        close_button.callback = close_callback
        view = discord.ui.View()
        view.add_item(close_button)

        await channel.send(content=member.mention, embed=embed_ticket, view=view)

        embed_success = discord.Embed(
            title="✅ 票單已開啟",
            description=f"已為您開啟票單 {channel.mention}，請前往該頻道查看詳細資訊。",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed_success, ephemeral=True)

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)

    await interaction.response.send_message(embed=embed, view=view)

# ---------- 查看開單紀錄 ----------
@bot.tree.command(name="ticket_logs", description="查看最近的開單紀錄（管理員）")
@app_commands.default_permissions(administrator=True)
async def ticket_logs(interaction: discord.Interaction):
    if not ticket_logs:
        embed = discord.Embed(
            title="📭 目前沒有任何開單紀錄",
            color=discord.Color.gray()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="📋 開單紀錄",
        description=f"顯示最近 {min(5, len(ticket_logs))} 筆紀錄",
        color=discord.Color.gold()
    )
    
    for idx, (channel_id, data) in enumerate(list(ticket_logs.items())[-5:], 1):
        user = interaction.guild.get_member(data["user"])
        user_name = user.mention if user else "未知使用者"
        embed.add_field(
            name=f"#{idx} 頻道 <#{channel_id}>",
            value=f"👤 {user_name}\n📂 {data['category']}\n🕒 {data['created_at']}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------- 清除所有分類（危險指令） ----------
@bot.tree.command(name="ticket_clear_all", description="清除此伺服器的所有分類（管理員）")
@app_commands.default_permissions(administrator=True)
async def ticket_clear_all(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    categories = get_guild_categories(guild_id)
    
    if not categories:
        embed = discord.Embed(
            title="📭 已經沒有任何分類",
            color=discord.Color.gray()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    count = len(categories)
    set_guild_categories(guild_id, {})
    
    embed = discord.Embed(
        title="🗑️ 已清除所有分類",
        description=f"已移除 {count} 個分類",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------- 啟動機器人 ----------
if __name__ == "__main__":
    bot.run(TOKEN)
