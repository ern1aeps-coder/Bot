import discord
from discord.ext import commands
import json
import os
import random
import asyncio
from datetime import timedelta
import yt_dlp  # Müzik için eklendi

DATA_FILE = "futbol_veriler.txt"
kullanici_aramalari = {}  # Müzik aramalarını hafızada tutmak için eklendi

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=["a ", "A ", "a", "A"], intents=intents, case_insensitive=True, help_command=None)

# ==========================================
# ⚽ FUTBOL VERİLERİ VE FONKSİYONLARI
# ==========================================

ALT_LIG_TAKIMLARI = ["Üsküdar Malatyaspor", "Amedspor", "Çorum FK", "Erzurumspor FK", "Bandırmaspor", "Boluspor", "Sakaryaspor", "Kocaelispor", "Gençlerbirliği"]
SUPER_LIG_TAKIMLARI = ["Galatasaray", "Fenerbahçe", "Beşiktaş", "Trabzonspor", "Başakşehir", "Antalyaspor", "Kayserispor"]
BUNDESLIGA_TAKIMLARI = ["Bayern München", "Borussia Dortmund", "Bayer Leverkusen", "RB Leipzig", "Eintracht Frankfurt", "VfB Stuttgart", "Werder Bremen"]
PREMIER_LEAGUE_TAKIMLARI = ["Manchester City", "Arsenal", "Liverpool", "Manchester United", "Chelsea", "Tottenham Hotspur", "Aston Villa"]
LA_LIGA_TAKIMLARI = ["Real Madrid", "Barcelona", "Atletico Madrid", "Real Sociedad", "Athletic Bilbao", "Villarreal", "Real Betis"]
SERIE_A_TAKIMLARI = ["Inter", "AC Milan", "Juventus", "Napoli", "Atalanta", "AS Roma", "Lazio"]

MEVKILER = ["KL", "STP", "SĞB", "SLB", "DOS", "OS", "OOS", "SLK", "SĞK", "SNT"]
NPC_ISIMLERI = ["Ahmet Can", "Mert Demir", "Burak Yılmaz", "Emre Çelik", "Kerem Arslan", "Caner Erkin", "Semih Kaya", "Ozan Tufan", "Yusuf Yazıcı", "Arda Turan", "Volkan Demirel"]

class MacSecimView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=15.0)
        self.author = author
        self.secim = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.author:
            return True
        await interaction.response.send_message("❌ Bu butonları sadece maçı oynayan oyuncu kullanabilir!", ephemeral=True)
        return False

    @discord.ui.button(label="Pas Ver", style=discord.ButtonStyle.primary, emoji="1️⃣")
    async def pas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.secim = "pas"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Şut Çek", style=discord.ButtonStyle.success, emoji="2️⃣")
    async def sut_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.secim = "sut"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Çalım At", style=discord.ButtonStyle.danger, emoji="3️⃣")
    async def calim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.secim = "calim"
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self):
        self.secim = "pas"
        self.stop()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    content = message.content
    if content.lower().startswith("a") and len(content) > 1 and content[1].isalpha() and not content.startswith("a "):
        message.content = "a " + content[1:]
    await bot.process_commands(message)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {} 
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {} 

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_league_name(team):
    if team in ALT_LIG_TAKIMLARI: return "Alt Lig"
    if team in SUPER_LIG_TAKIMLARI: return "Süper Lig"
    if team in BUNDESLIGA_TAKIMLARI: return "Bundesliga"
    if team in PREMIER_LEAGUE_TAKIMLARI: return "Premier League"
    if team in LA_LIGA_TAKIMLARI: return "La Liga"
    return "Serie A"

def init_league_tables(data):
    if "league_tables" not in data:
        data["league_tables"] = {}
        for l_name, pool in [("Alt Lig", ALT_LIG_TAKIMLARI), ("Süper Lig", SUPER_LIG_TAKIMLARI), ("Bundesliga", BUNDESLIGA_TAKIMLARI), ("Premier League", PREMIER_LEAGUE_TAKIMLARI), ("La Liga", LA_LIGA_TAKIMLARI), ("Serie A", SERIE_A_TAKIMLARI)]:
            data["league_tables"][l_name] = {}
            for team in pool:
                if team != "Bay":
                    data["league_tables"][l_name][team] = {"O": 0, "G": 0, "B": 0, "M": 0, "AG": 0, "YG": 0, "P": 0, "oyuncu": None}

def update_players_in_leagues(data):
    init_league_tables(data)
    for l_name in data["league_tables"]:
        for team in data["league_tables"][l_name]:
            data["league_tables"][l_name][team]["oyuncu"] = None
            
    for uid, udata in data.items():
        if uid == "league_tables" or not isinstance(udata, dict) or not udata.get("registered", False):
            continue
        team = udata.get("team")
        p_name = udata.get("player_name")
        l_name = get_league_name(team)
        if l_name in data["league_tables"] and team in data["league_tables"][l_name]:
            data["league_tables"][l_name][team]["oyuncu"] = p_name

def generate_fixture(teams):
    if len(teams) % 2 != 0:
        teams.append("Bay")
    l = len(teams)
    fixtures = []
    temp_teams = teams[:]
    for round_num in range(l - 1):
        round_matches = []
        for i in range(l // 2):
            t1 = temp_teams[i]
            t2 = temp_teams[l - 1 - i]
            if t1 != "Bay" and t2 != "Bay":
                round_matches.append((t1, t2))
        fixtures.append(round_matches)
        temp_teams = [temp_teams[0]] + [temp_teams[-1]] + temp_teams[1:-1]
    second_half = []
    for round_matches in fixtures:
        revans = [(t2, t1) for t1, t2 in round_matches]
        second_half.append(revans)
    return fixtures + second_half

def check_user(user_id, data):
    uid = str(user_id)
    is_changed = False
    init_league_tables(data)
    
    if uid not in data:
        data[uid] = {
            "registered": False,
            "player_name": "",
            "position": "SNT",
            "team": "Üsküdar Malatyaspor",
            "value": 1.0,
            "training_count": 0,
            "skill": "Yok",
            "stats": {"guc": 10, "hiz": 10, "sut": 10},
            "current_week": 1,
            "fixture": {}
        }
        is_changed = True
    else:
        if "team" not in data[uid]:
            data[uid]["team"] = "Üsküdar Malatyaspor"
            is_changed = True
        if "current_week" not in data[uid]:
            data[uid]["current_week"] = 1
            is_changed = True
        if "value" in data[uid] and isinstance(data[uid]["value"], int):
            data[uid]["value"] = float(data[uid]["value"])
            is_changed = True
        if "fixture" not in data[uid] or not data[uid]["fixture"]:
            team = data[uid]["team"]
            l_name = get_league_name(team)
            pool = []
            if l_name == "Alt Lig": pool = ALT_LIG_TAKIMLARI
            elif l_name == "Süper Lig": pool = SUPER_LIG_TAKIMLARI
            elif l_name == "Bundesliga": pool = BUNDESLIGA_TAKIMLARI
            elif l_name == "Premier League": pool = PREMIER_LEAGUE_TAKIMLARI
            elif l_name == "La Liga": pool = LA_LIGA_TAKIMLARI
            else: pool = SERIE_A_TAKIMLARI
            
            raw_fix = generate_fixture(pool.copy())
            fix_dict = {}
            for idx, matches in enumerate(raw_fix, 1):
                fix_dict[str(idx)] = [{"ev": m[0], "dep": m[1], "oynandi": False, "skor": ""} for m in matches]
            data[uid]["fixture"] = fix_dict
            is_changed = True
        
    if is_changed:
        save_data(data)
    update_players_in_leagues(data)
    return uid

async def update_member_nickname(ctx, member, new_value, player_name, team):
    val_str = f"{new_value:.1f}".rstrip('0').rstrip('.') if isinstance(new_value, float) else str(new_value)
    new_nickname = f"[{val_str}M€] {player_name}"
    try:
        if len(new_nickname) > 32:
            new_nickname = new_nickname[:32]
        await member.edit(nick=new_nickname)
    except:
        pass

def kayitli_olmali():
    async def predicate(ctx):
        data = load_data()
        uid = str(ctx.author.id)
        if uid not in data or not data[uid].get("registered", False):
            await ctx.send(f"❌ {ctx.author.mention}, önce bir futbolcu kariyeri oluşturmalısın! Kayıt olmak için `abasla` yaz.")
            return False
        return True
    return commands.check(predicate)

def update_standings(l_table, t1, t2, g1, g2):
    if t1 in l_table:
        l_table[t1]["O"] += 1
        l_table[t1]["AG"] += g1
        l_table[t1]["YG"] += g2
        if g1 > g2:
            l_table[t1]["G"] += 1
            l_table[t1]["P"] += 3
        elif g1 == g2:
            l_table[t1]["B"] += 1
            l_table[t1]["P"] += 1
        else:
            l_table[t1]["M"] += 1
    if t2 in l_table:
        l_table[t2]["O"] += 1
        l_table[t2]["AG"] += g2
        l_table[t2]["YG"] += g1
        if g2 > g1:
            l_table[t2]["G"] += 1
            l_table[t2]["P"] += 3
        elif g2 == g1:
            l_table[t2]["B"] += 1
            l_table[t2]["P"] += 1
        else:
            l_table[t2]["M"] += 1

@bot.event
async def on_ready():
    print("----------------------------------------")
    print(f"✅ Bot Aktif: {bot.user} olarak giriş yapıldı!")
    print("----------------------------------------")
    await bot.change_presence(activity=discord.Game(name="ahelp | Futbol & Müzik"))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        remaining = timedelta(seconds=int(error.retry_after))
        await ctx.send(f"⏳ Bu komut için beklemedesin! Kalan süre: **{remaining}**")
    elif isinstance(error, commands.CheckFailure):
        pass
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        raise error

# ==========================================
# 🛠️ YARDIM KOMUTU (FUTBOL + MÜZİK)
# ==========================================

@bot.command(name="help", aliases=["yardım", "yardim"])
async def custom_help(ctx):
    embed = discord.Embed(title="🌟 Futbol Kariyer & Müzik Botu Menüsü", color=discord.Color.green())
    
    embed.add_field(name="📝 Kayıt & Profil", value="`abasla` (Kayıt Ol)\n`aprofil` (Futbolcu kartını gör)\n`asifirla` (Kariyerini sıfırla)", inline=False)
    embed.add_field(name="🔄 Transfer & Lig", value="`ateklifler` (Kulüp teklifleri al)\n`apuandurumu` (Lig puan tablosunu gör)\n`afikstur [hafta]` (Maç fikstürü)", inline=False)
    embed.add_field(name="🏋️ Gelişim & Maç", value="`aantrenman` (Stat ve değer kas)\n`amac` (Canlı butonlu maç yap)\n`apenalti <sol/orta/sag>`", inline=False)
    
    embed.add_field(name="🎵 Müzik Komutları", value="`amüzikara <şarkı>` (YouTube'da 12 şarkı arar)\n`açal <numara>` (Aramadan çıkan şarkıyı çalar)\n`akapat` (Müziği durdurur ve çıkar)", inline=False)
    
    await ctx.send(embed=embed)

# ==========================================
# ⚽ FUTBOL KOMUTLARI
# ==========================================

@bot.command(name="basla", aliases=["start"])
async def basla(ctx):
    data = load_data()
    uid = check_user(ctx.author.id, data)
    
    if data[uid]["registered"]:
        await ctx.send(f"❌ {ctx.author.mention}, zaten **{data[uid]['player_name']}** olarak kayıtlısın! Sıfırlamak için `asifirla` yazabilirsin.")
        return

    await ctx.send(f"⚽ **Futbol Kariyerine Hoş Geldin {ctx.author.mention}!**\nFutbolcunun **Adını ve Soyadını** yaz:")

    def check_msg(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg1 = await bot.wait_for("message", check=check_msg, timeout=30.0)
        p_name = msg1.content.strip()
    except:
        await ctx.send("⏰ Süre bitti! Kayıt iptal edildi.")
        return

    mevki_str = ", ".join(MEVKILER)
    await ctx.send(f"Harika! Şimdi mevkini seç:\n📌 Mevkiler: **{mevki_str}**\n*(Örn: SNT, KL, OOS, STP yaz)*")

    try:
        msg2 = await bot.wait_for("message", check=check_msg, timeout=30.0)
        pos = msg2.content.strip().upper()
        if pos not in MEVKILER:
            pos = "SNT"
    except:
        pos = "SNT"

    assigned_skill = random.choice(["Füze Şutör", "Çevik Çalımcı", "Duvar Kaleci", "Kreatif Maestro", "Amansız Pres"])
    secilen_takim = random.choice(["Üsküdar Malatyaspor", "Amedspor", "Çorum FK", "Erzurumspor FK"])
    
    raw_fix = generate_fixture(ALT_LIG_TAKIMLARI.copy())
    fix_dict = {}
    for idx, matches in enumerate(raw_fix, 1):
        fix_dict[str(idx)] = [{"ev": m[0], "dep": m[1], "oynandi": False, "skor": ""} for m in matches]

    data[uid]["registered"] = True
    data[uid]["player_name"] = p_name
    data[uid]["position"] = pos
    data[uid]["skill"] = assigned_skill
    data[uid]["team"] = secilen_takim
    data[uid]["value"] = 1.0
    data[uid]["training_count"] = 0
    data[uid]["current_week"] = 1
    data[uid]["fixture"] = fix_dict
    
    update_players_in_leagues(data)
    save_data(data)

    await update_member_nickname(ctx, ctx.author, data[uid]["value"], p_name, secilen_takim)

    embed = discord.Embed(title="🎉 Kariyer Başlatıldı!", color=discord.Color.gold())
    embed.add_field(name="Futbolcu Adı", value=p_name, inline=True)
    embed.add_field(name="Mevki", value=pos, inline=True)
    embed.add_field(name="Kulüp", value=secilen_takim, inline=True)
    embed.add_field(name="Piyasa Değeri", value=f"**{data[uid]['value']}M €**", inline=True)
    embed.add_field(name="Özel Yetenek", value=assigned_skill, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="sıfırla", aliases=["sifirla", "kariyersifirla"])
@kayitli_olmali()
async def sifirla(ctx):
    data = load_data()
    uid = check_user(ctx.author.id, data)

    await ctx.send(f"⚠️ **{ctx.author.mention}, kariyerini tamamen sıfırlamak istediğine emin misin?** (Tüm değerin ve istatistiklerin silinecek!)\nOnaylamak için `evet` yaz.")

    def check_m(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", check=check_m, timeout=15.0)
        if msg.content.strip().lower() == "evet":
            data[uid] = {
                "registered": False,
                "player_name": "",
                "position": "SNT",
                "team": "Üsküdar Malatyaspor",
                "value": 1.0,
                "training_count": 0,
                "skill": "Yok",
                "stats": {"guc": 10, "hiz": 10, "sut": 10},
                "current_week": 1,
                "fixture": {}
            }
            update_players_in_leagues(data)
            save_data(data)
            await ctx.send("💥 Kariyerin başarıyla sıfırlandı! `abasla` yazarak 0'dan yeni kariyer açabilirsin.")
        else:
            await ctx.send("❌ Kariyer sıfırlama işlemi iptal edildi.")
    except:
        await ctx.send("⏰ Süre doldu, işlem iptal edildi.")

@bot.command(name="profil", aliases=["profile", "p"])
@kayitli_olmali()
async def profil(ctx):
    data = load_data()
    uid = check_user(ctx.author.id, data)
    user_data = data[uid]
    val_str = f"{user_data['value']:.1f}".rstrip('0').rstrip('.')

    embed = discord.Embed(title=f"⚽ {user_data['player_name']} - Futbolcu Kartı", color=discord.Color.blue())
    embed.add_field(name="Takım & Mevki", value=f"Kulüp: **{user_data['team']}**\nMevki: **{user_data['position']}**", inline=False)
    embed.add_field(name="Sezon Durumu", value=f"📅 Hafta: **{user_data['current_week']}**", inline=True)
    embed.add_field(name="Piyasa Değeri", value=f"💰 **{val_str}M €**", inline=True)
    embed.add_field(name="Özel Yetenek", value=f"✨ *{user_data['skill']}*", inline=True)
    embed.add_field(name="Antrenman İlerlemesi", value=f"🏋️ **{user_data['training_count']}/10**", inline=False)
    
    stats = user_data["stats"]
    stats_str = f"⚡ Güç: {stats['guc']} | 🏃 Hız: {stats['hiz']} | 🎯 Şut: {stats['sut']}"
    embed.add_field(name="Özellikler", value=stats_str, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="puandurumu", aliases=["puan", "standings", "lig"])
@kayitli_olmali()
async def puandurumu(ctx):
    data = load_data()
    uid = check_user(ctx.author.id, data)
    user = data[uid]
    team = user["team"]
    league_name = get_league_name(team)
    
    update_players_in_leagues(data)
    league_table = data["league_tables"].get(league_name, {})
    
    sorted_table = sorted(
        league_table.items(),
        key=lambda x: (x[1]["P"], (x[1]["AG"] - x[1]["YG"]), x[1]["AG"]),
        reverse=True
    )
    
    embed = discord.Embed(title=f"📊 {league_name} Puan Durumu (Hafta {user['current_week']})", color=discord.Color.gold())
    
    table_str = "```text\n"
    table_str += f"{'S':<2} | {'Takım / Oyuncu':<21} | {'O':<2} | {'G':<2} | {'B':<2} | {'M':<2} | {'AV':<3} | {'P':<2}\n"
    table_str += "-" * 60 + "\n"
    
    for idx, (t_name, stats) in enumerate(sorted_table, 1):
        display_name = t_name
        if stats["oyuncu"]:
            display_name = f"{t_name} ({stats['oyuncu']})"
        if len(display_name) > 21:
            display_name = display_name[:18] + "..."
        
        av = stats["AG"] - stats["YG"]
        table_str += f"{idx:<2} | {display_name:<21} | {stats['O']:<2} | {stats['G']:<2} | {stats['B']:<2} | {stats['M']:<2} | {av:<3} | {stats['P']:<2}\n"
        
    table_str += "```"
    embed.description = table_str
    embed.set_footer(text="Takımınızda gerçek oyuncu varsa parantez içinde ismi yazar!")
    await ctx.send(embed=embed)

@bot.command(name="fikstür", aliases=["fikstur", "fixture"])
@kayitli_olmali()
async def fikstur(ctx, hafta: int = None):
    data = load_data()
    uid = check_user(ctx.author.id, data)
    user = data[uid]

    target_week = hafta if hafta else user["current_week"]
    fix = user.get("fixture", {})
    
    if str(target_week) not in fix:
        await ctx.send(f"❌ Geçersiz hafta! (Mevcut hafta: {user['current_week']})")
        return

    matches = fix[str(target_week)]
    embed = discord.Embed(title=f"📅 Sezon Fikstürü — Hafta {target_week}", color=discord.Color.teal())
    embed.description = f"Senin Takımın: **{user['team']}**"

    match_list_str = ""
    for m in matches:
        ev = m["ev"]
        dep = m["dep"]
        status = f"✅ {m['skor']}" if m["oynandi"] else "⏰ Oynanmadı"
        if ev == user["team"] or dep == user["team"]:
            match_list_str += f"⭐ **{ev} vs {dep}** — *{status}*\n"
        else:
            match_list_str += f"{ev} vs {dep} — *{status}*\n"

    embed.add_field(name="Maç Programı", value=match_list_str if match_list_str else "Bu hafta maç yok.", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="teklifler", aliases=["teklif", "transfers"])
@kayitli_olmali()
async def teklifler(ctx):
    data = load_data()
    uid = check_user(ctx.author.id, data)
    user = data[uid]
    val = user["value"]
    
    if val <= 5: gelen_teklifler = random.sample(ALT_LIG_TAKIMLARI, 2)
    elif val <= 12: gelen_teklifler = random.sample(SUPER_LIG_TAKIMLARI, 2)
    elif val <= 25: gelen_teklifler = random.sample(BUNDESLIGA_TAKIMLARI + SERIE_A_TAKIMLARI, 2)
    elif val <= 40: gelen_teklifler = random.sample(LA_LIGA_TAKIMLARI + PREMIER_LEAGUE_TAKIMLARI, 2)
    else: gelen_teklifler = random.sample(PREMIER_LEAGUE_TAKIMLARI + LA_LIGA_TAKIMLARI + SERIE_A_TAKIMLARI + BUNDESLIGA_TAKIMLARI, 3)

    embed = discord.Embed(title="🔄 Dünya Transfer Piyasası & Kulüp Teklifleri", color=discord.Color.purple())
    val_str = f"{val:.1f}".rstrip('0').rstrip('.')
    embed.description = f"Mevcut Kulübün: **{user['team']}**\nPiyasa Değerin: **{val_str}M €**\n\nSeni isteyen kulüpler:"
    
    for i, takim in enumerate(gelen_teklifler, 1):
        embed.add_field(name=f"{i}. Seçenek: {takim}", value=f"İmzalamak için `aimza {i}` yaz.", inline=False)
    
    embed.set_footer(text="Transfer seçimi için 30 saniyen var!")
    await ctx.send(embed=embed)

    def check_m(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", check=check_m, timeout=30.0)
        content = msg.content.strip().lower()
        if content.startswith("aimza"):
            secim_idx = int(content.split()[1]) - 1
            secilen_takim = gelen_teklifler[secim_idx]
            user["team"] = secilen_takim
            
            l_name = get_league_name(secilen_takim)
            pool = ALT_LIG_TAKIMLARI
            if l_name == "Süper Lig": pool = SUPER_LIG_TAKIMLARI
            elif l_name == "Bundesliga": pool = BUNDESLIGA_TAKIMLARI
            elif l_name == "Premier League": pool = PREMIER_LEAGUE_TAKIMLARI
            elif l_name == "La Liga": pool = LA_LIGA_TAKIMLARI
            elif l_name == "Serie A": pool = SERIE_A_TAKIMLARI
            
            raw_fix = generate_fixture(pool.copy())
            fix_dict = {}
            for idx, matches in enumerate(raw_fix, 1):
                fix_dict[str(idx)] = [{"ev": m[0], "dep": m[1], "oynandi": False, "skor": ""} for m in matches]
            user["fixture"] = fix_dict
            user["current_week"] = 1

            update_players_in_leagues(data)
            save_data(data)
            await update_member_nickname(ctx, ctx.author, user["value"], user["player_name"], secilen_takim)
            await ctx.send(f"✍️ Resmen **{secilen_takim}** takımına transfer oldun! Fikstür yeni ligine göre sıfırlandı. 🚀🔥")
        else:
            await ctx.send("❌ Geçersiz komut, transfer iptal edildi.")
    except:
        pass

@bot.command(name="antrenman", aliases=["antrenmanyap", "train"])
@kayitli_olmali()
@commands.cooldown(1, 3600, commands.BucketType.user)
async def antrenman(ctx):
    data = load_data()
    uid = check_user(ctx.author.id, data)
    user = data[uid]
    
    user["training_count"] += 1
    stat_to_improve = random.choice(["guc", "hiz", "sut"])
    user["stats"][stat_to_improve] += random.randint(1, 3)
    msg = f"🏋️ **{user['player_name']}** antrenman yaptı! `{stat_to_improve.upper()}` statı arttı."
    
    if user["training_count"] >= 10:
        user["training_count"] = 0
        user["value"] += 1.0
        msg += f"\n\n🌟 **MÜKEMMEL GELİŞİM!** Piyasa değerin **+1M €** artarak **{user['value']}M €** oldu!"
        await update_member_nickname(ctx, ctx.author, user["value"], user["player_name"], user["team"])

    save_data(data)
    val_str = f"{user['value']:.1f}".rstrip('0').rstrip('.')
    await ctx.send(msg + f"\n📊 Antrenman İlerlemesi: **{user['training_count']}/10** | Değer: **{val_str}M €**")

@bot.command(name="penaltı", aliases=["penalti", "penalty"])
@kayitli_olmali()
@commands.cooldown(1, 7200, commands.BucketType.user)
async def penalti(ctx, kose: str = None):
    data = load_data()
    uid = check_user(ctx.author.id, data)
    
    if not kose or kose.lower() not in ["sol", "orta", "sag"]:
        await ctx.send("❌ Örnek kullanım: `apenalti sol` (sol, orta, sag)")
        ctx.command.reset_cooldown(ctx)
        return

    user = data[uid]
    pos = user["position"]
    rakip_secimi = random.choice(["sol", "orta", "sag"])
    user_kose = kose.lower()
    
    if pos == "KL":
        if user_kose == rakip_secimi:
            user["value"] += 1.0
            save_data(data)
            await update_member_nickname(ctx, ctx.author, user["value"], user["player_name"], user["team"])
            await ctx.send(f"🧤 **PENALTI KURTARILDI!** Rakip **{rakip_secimi}** vurdu, tuttun!\n💰 Değerin **+1M €** arttı (**{user['value']}M €**)")
        else:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(f"❌ **GOL OLDU!** Sen **{user_kose}** dedin, rakip **{rakip_secimi}** köşeye vurdu.")
    else:
        if user_kose != rakip_secimi:
            user["value"] += 1.0
            save_data(data)
            await update_member_nickname(ctx, ctx.author, user["value"], user["player_name"], user["team"])
            await ctx.send(f"⚽ **GOL!** Kaleciyi **{rakip_secimi}** köşeye yatırdın!\n💰 Değerin **+1M €** arttı (**{user['value']}M €**)")
        else:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(f"❌ **KAÇTI!** Kaleci **{rakip_secimi}** köşeden çıkardı!")

@bot.command(name="maç", aliases=["mac", "match"])
@kayitli_olmali()
@commands.cooldown(1, 1800, commands.BucketType.user)
async def mac(ctx):
    data = load_data()
    uid = check_user(ctx.author.id, data)
    user = data[uid]
    
    kendi_takimi = user["team"]
    curr_week = str(user["current_week"])
    league_name = get_league_name(kendi_takimi)
    league_table = data["league_tables"][league_name]
    
    week_matches = user["fixture"].get(curr_week, [])
    rakip_takim = "Bilinmeyen Rakip"
    match_index = -1
    
    for idx, m in enumerate(week_matches):
        if m["ev"] == kendi_takimi:
            rakip_takim = m["dep"]
            match_index = idx
            break
        elif m["dep"] == kendi_takimi:
            rakip_takim = m["ev"]
            match_index = idx
            break
            
    if rakip_takim == "Bilinmeyen Rakip":
        pool = []
        l_name = league_name
        if l_name == "Alt Lig": pool = ALT_LIG_TAKIMLARI
        elif l_name == "Süper Lig": pool = SUPER_LIG_TAKIMLARI
        elif l_name == "Bundesliga": pool = BUNDESLIGA_TAKIMLARI
        elif l_name == "Premier League": pool = PREMIER_LEAGUE_TAKIMLARI
        elif l_name == "La Liga": pool = LA_LIGA_TAKIMLARI
        else: pool = SERIE_A_TAKIMLARI
        rakip_takim = random.choice([t for t in pool if t != kendi_takimi])

    await ctx.send(f"🏟️ **CANLI MAÇ BAŞLADI! (Hafta {user['current_week']})**\n{kendi_takimi} vs **{rakip_takim}**\nDakika: `01'` — Hakem düdüğünü çaldı, maç başladı.")
    
    interactive_minutes = sorted(random.sample([18, 34, 51, 72, 85], 2))
    bizim_gol_sayisi = 0
    rakip_gol_sayisi = 0
    user_gol = 0
    user_asist = 0
    
    for minute in range(2, 91):
        await asyncio.sleep(1.2)
        mesafe_orani = random.choice([1, 2, 3, 4, 5, 6, 7])
        if mesafe_orani == 1: bolge_adi, ceza_sahasinda_mi = "Kendi Ceza Sahamız", "kendi_ceza"
        elif mesafe_orani == 2: bolge_adi, ceza_sahasinda_mi = "Kendi Sahamız", "kendi_saha"
        elif mesafe_orani in [3, 4, 5]: bolge_adi, ceza_sahasinda_mi = "Orta Saha", "orta_saha"
        elif mesafe_orani == 6: bolge_adi, ceza_sahasinda_mi = "Rakip Saha", "rakip_saha"
        else: bolge_adi, ceza_sahasinda_mi = "Rakip Ceza Sahası", "rakip_ceza"
        
        top_pozisyon_metri = f"📍 Bölge: **{bolge_adi}** | {kendi_takimi} vs {rakip_takim}"
        skor_metni = f"**Skor:**\n{kendi_takimi} {bizim_gol_sayisi} - {rakip_gol_sayisi} {rakip_takim}"
        
        if minute in interactive_minutes:
            view = MacSecimView(ctx.author)
            await ctx.send(f"⏰ **{minute}'**\n\n👉 **Hamleni seç!** *(15 saniye)*\n{top_pozisyon_metri}\n\n{skor_metni}", view=view)
            await view.wait()
            secim = view.secim if view.secim else "pas"

            basari_puani = user["stats"]["sut"] + user["stats"]["hiz"] + random.randint(1, 35)
            
            if secim == "pas":
                if basari_puani > 38:
                    bizim_gol_sayisi += 1
                    user_asist += 1
                    await ctx.send(f"⏰ **{minute}'**\n\n🎯 Harika asist! **GOL!** ⚽ *(+1 Asist)*\n{top_pozisyon_metri}\n\n**Skor:**\n{kendi_takimi} {bizim_gol_sayisi} - {rakip_gol_sayisi} {rakip_takim}")
                else:
                    await ctx.send(f"⏰ **{minute}'**\n\n❌ Pas denemesinde savunma araya girdi.")
            elif secim == "sut":
                if ceza_sahasinda_mi == "kendi_ceza":
                    if basari_puani < 50:
                        rakip_gol_sayisi += 1
                        await ctx.send(f"⏰ **{minute}'**\n\n😱 Kendi ceza sahanda riskli şut denedin, kendi kalemize gol attık! ⚽❌\n{top_pozisyon_metri}\n\n**Skor:**\n{kendi_takimi} {bizim_gol_sayisi} - {rakip_gol_sayisi} {rakip_takim}")
                    else:
                        await ctx.send(f"⏰ **{minute}'**\n\n😅 Tehlikeyi uzaklaştırdın.")
                elif ceza_sahasinda_mi == "rakip_ceza":
                    if basari_puani > 35:
                        bizim_gol_sayisi += 1
                        user_gol += 1
                        await ctx.send(f"⏰ **{minute}'**\n\n🔥 Ağlar sarsıldı, **GOL!** ⚽🚀 *(+1 Gol)*\n{top_pozisyon_metri}\n\n**Skor:**\n{kendi_takimi} {bizim_gol_sayisi} - {rakip_gol_sayisi} {rakip_takim}")
                    else:
                        await ctx.send(f"⏰ **{minute}'**\n\n💥 Kaleci şutu kornere çeldi!")
                else:
                    await ctx.send(f"⏰ **{minute}'**\n\n⚠️ Uzaktan şut auta gitti.")
            elif secim == "calim":  
                if basari_puani > 35:
                    if ceza_sahasinda_mi == "rakip_ceza":
                        bizim_gol_sayisi += 1
                        user_gol += 1
                        await ctx.send(f"⏰ **{minute}'**\n\n✨ Şık çalımlarla geçip vurdun, **GOL!** ⚽🎯 *(+1 Gol)*\n{top_pozisyon_metri}\n\n**Skor:**\n{kendi_takimi} {bizim_gol_sayisi} - {rakip_gol_sayisi} {rakip_takim}")
                    else:
                        await ctx.send(f"⏰ **{minute}'**\n\n✨ Rakipleri çalımlarla ekarte ettin.")
                else:
                    if ceza_sahasinda_mi == "kendi_ceza":
                        rakip_gol_sayisi += 1
                        await ctx.send(f"⏰ **{minute}'**\n\n🛑 Kendi ceza sahanda topu kaptırdın ve gol yedik! ⚽❌\n{top_pozisyon_metri}\n\n**Skor:**\n{kendi_takimi} {bizim_gol_sayisi} - {rakip_gol_sayisi} {rakip_takim}")
                    else:
                        await ctx.send(f"⏰ **{minute}'**\n\n🛑 Çalım denemesinde topu kaptırdın.")
            await asyncio.sleep(1.0)
        else:
            olay_tipi = random.random()
            if olay_tipi < 0.04:
                bizim_gol_sayisi += 1
                asist_notu = " *(Asistini sen yaptın!)*" if random.random() < 0.35 else ""
                if "asist_notu" in locals() and asist_notu: user_asist += 1
                npc_isim = random.choice(NPC_ISIMLERI)
                await ctx.send(f"⏰ **{minute}'**\n⚽ **GOL!** **{npc_isim}** ağları sarstı!{asist_notu}\n{top_pozisyon_metri}\n**Skor:** {kendi_takimi} {bizim_gol_sayisi} - {rakip_gol_sayisi} {rakip_takim}")
            elif olay_tipi < 0.08:
                rakip_gol_sayisi += 1
                await ctx.send(f"⏰ **{minute}'**\n❌ **GOL YEDİK!** Rakip skoru buldu.\n{top_pozisyon_metri}\n**Skor:** {kendi_takimi} {bizim_gol_sayisi} - {rakip_gol_sayisi} {rakip_takim}")
            elif olay_tipi < 0.14:
                await ctx.send(f"⏰ **{minute}'**\n⚡ Orta alanda sert mücadele devam ediyor.\n{top_pozisyon_metri}")

    skor_str = f"{bizim_gol_sayisi}-{rakip_gol_sayisi}"
    
    kazanilan_deger = (user_gol * 1.0) + (user_asist * 0.5)
    user["value"] += kazanilan_deger
    
    if bizim_gol_sayisi > rakip_gol_sayisi:
        sonuc_metni = f"🏁 **MAÇ BİTTİ!** Galibiyet! `{kendi_takimi} {bizim_gol_sayisi} - {rakip_gol_sayisi} {rakip_takim}`\n⚽ {user_gol} Gol, 👟 {user_asist} Asist ile değerin **+{kazanilan_deger}M €** artarak **{user['value']}M €** oldu!"
        await update_member_nickname(ctx, ctx.author, user["value"], user["player_name"], user["team"])
    elif bizim_gol_sayisi < rakip_gol_sayisi:
        ctx.command.reset_cooldown(ctx)
        sonuc_metni = f"🏁 **MAÇ BİTTİ!** Mağlubiyet... `{kendi_takimi} {bizim_gol_sayisi} - {rakip_gol_sayisi} {rakip_takim}`\n⚽ {user_gol} Gol, 👟 {user_asist} Asist sayesinde değerin **+{kazanilan_deger}M €** artarak **{user['value']}M €** oldu."
        if kazanilan_deger > 0: await update_member_nickname(ctx, ctx.author, user["value"], user["player_name"], user["team"])
    else:
        ctx.command.reset_cooldown(ctx)
        sonuc_metni = f"🏁 **MAÇ BİTTİ!** Beraberlik: `{kendi_takimi} {bizim_gol_sayisi} - {rakip_gol_sayisi} {rakip_takim}`\n⚽ {user_gol} Gol, 👟 {user_asist} Asist ile değerin **+{kazanilan_deger}M €** artarak **{user['value']}M €** oldu."
        if kazanilan_deger > 0: await update_member_nickname(ctx, ctx.author, user["value"], user["player_name"], user["team"])

    update_standings(league_table, kendi_takimi, rakip_takim, bizim_gol_sayisi, rakip_gol_sayisi)

    for idx, m in enumerate(week_matches):
        if m["ev"] == kendi_takimi or m["dep"] == kendi_takimi:
            m["oynandi"] = True
            m["skor"] = skor_str
        else:
            if not m["oynandi"]:
                g1 = random.randint(0, 3)
                g2 = random.randint(0, 3)
                m["oynandi"] = True
                m["skor"] = f"{g1}-{g2}"
                update_standings(league_table, m["ev"], m["dep"], g1, g2)
    
    user["current_week"] += 1
    update_players_in_leagues(data)
    save_data(data)

    await ctx.send(sonuc_metni + f"\n📅 Hafta atlandı. Yeni Hafta: **{user['current_week']}** (`apuandurumu` yazarak puan tablosunu inceleyebilirsin)")

# ==========================================
# 🎵 MÜZİK KOMUTLARI
# ==========================================

@bot.command(name="müzikara", aliases=["muzikara", "search"])
async def muzikara(ctx, *, sarki_adi: str):
    if not ctx.author.voice:
        return await ctx.send(f"❌ {ctx.author.mention}, müzik aramak için önce bir ses kanalına girmelisin!")

    mesaj = await ctx.send(f"🔍 `{sarki_adi}` için YouTube'da aranıyor, lütfen bekle...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': 'True',
        'quiet': True,
        'extract_flat': True 
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch12:{sarki_adi}", download=False)
            entries = info.get('entries', [])
            
            if not entries:
                return await mesaj.edit(content="❌ Hiçbir sonuç bulunamadı.")

            if ctx.guild.id not in kullanici_aramalari:
                kullanici_aramalari[ctx.guild.id] = {}
            
            kullanici_aramalari[ctx.guild.id][ctx.author.id] = entries

            embed = discord.Embed(title=f"🎵 Arama Sonuçları: {sarki_adi}", color=discord.Color.brand_red())
            aciklama = ""
            for i, entry in enumerate(entries, 1):
                baslik = entry.get('title', 'Bilinmeyen Şarkı')
                aciklama += f"**{i}.** {baslik}\n"
            
            embed.description = aciklama
            embed.set_footer(text="Açmak istediğin şarkı için: açal <numara> (Örn: açal 1)")
            
            await mesaj.delete()
            await ctx.send(embed=embed)

        except Exception as e:
            await mesaj.edit(content="❌ Arama sırasında bir hata oluştu.")
            print(f"Müzik Arama Hatası: {e}")

@bot.command(name="çal", aliases=["cal", "play"])
async def cal(ctx, numara: int = None):
    if not ctx.author.voice:
        return await ctx.send("❌ Önce bir ses kanalına katılmalısın!")
        
    if numara is None:
        return await ctx.send("❌ Lütfen listeden bir numara seç! Örnek: `açal 12`")

    guild_id = ctx.guild.id
    author_id = ctx.author.id
    
    if guild_id not in kullanici_aramalari or author_id not in kullanici_aramalari[guild_id]:
        return await ctx.send("❌ Önce bir müzik aratmalısın! Örnek: `amüzikara Galatasaray Marşı`")
        
    entries = kullanici_aramalari[guild_id][author_id]
    
    if numara < 1 or numara > len(entries):
        return await ctx.send(f"❌ Geçersiz numara! Lütfen 1 ile {len(entries)} arasında bir sayı gir.")
        
    secilen_sarki = entries[numara - 1]
    video_url = secilen_sarki.get('url')
    if not video_url:
        video_url = f"https://www.youtube.com/watch?v={secilen_sarki.get('id')}"

    voice_channel = ctx.author.voice.channel
    voice_client = ctx.voice_client
    
    if not voice_client:
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    if voice_client.is_playing():
        voice_client.stop()

    mesaj = await ctx.send(f"⏳ **{secilen_sarki.get('title')}** yükleniyor...")

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }
    YDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': 'True', 'quiet': True}

    try:
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(video_url, download=False)
            url2 = info['url']
            
            source = await discord.FFmpegOpusAudio.from_probe(url2, **FFMPEG_OPTIONS)
            voice_client.play(source)

        await mesaj.edit(content=f"▶️ **Şu an çalıyor:** {secilen_sarki.get('title')}")
    except Exception as e:
        await mesaj.edit(content="❌ Şarkı oynatılamadı. Format desteklenmiyor olabilir veya sisteminde FFmpeg yüklü değil.")
        print(f"Oynatma Hatası: {e}")

@bot.command(name="kapat", aliases=["ayrıl", "ayril", "çık", "dur", "stop"])
async def kapat(ctx):
    voice_client = ctx.voice_client
    if voice_client:
        await voice_client.disconnect()
        await ctx.send("🛑 Müzik durduruldu ve ses kanalından ayrıldım.")
    else:
        await ctx.send("❌ Şu anda herhangi bir ses kanalında değilim.")

bot.run("DISCORD_TOKEN")
