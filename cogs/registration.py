# ── Jarcord — member registration (form modal + staff review) ──
import discord
from discord.ext import commands

from db import conn, get_setting, set_setting
from cogs.profile import resolve_roblox
from ui import ACCENT, embed

APPROVED = discord.Colour(0x22C55E)
DENIED = discord.Colour(0xEF4444)


def application_embed(app, applicant: discord.User | discord.Member = None) -> discord.Embed:
    colour = {"approved": APPROVED, "denied": DENIED}.get(app["status"], ACCENT)
    e = embed(title="Registration", colour=colour)
    if applicant is not None:
        e.set_author(name=str(applicant), icon_url=applicant.display_avatar.url)
        e.set_thumbnail(url=applicant.display_avatar.url)
    e.add_field(name="Member", value=f"<@{app['user_id']}>", inline=True)
    e.add_field(name="Roblox", value=app["roblox"], inline=True)
    e.add_field(name="Age group", value=app["age_group"] or "—", inline=True)
    e.add_field(name="Pronouns", value=app["pronouns"] or "—", inline=True)
    e.add_field(name="Timezone", value=app["timezone"] or "—", inline=True)
    e.add_field(name="Available", value=app["availability"] or "—", inline=False)
    state = "awaiting review" if app["status"] == "pending" else app["status"]
    e.set_footer(text=f"Application #{app['id']} · {state}")
    return e


class ReviewView(discord.ui.View):
    """Persistent — custom_ids are static, the application is found by message id."""

    def __init__(self):
        super().__init__(timeout=None)

    async def _resolve(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "Only staff with Manage Roles can review registrations.", ephemeral=True
            )
            return None
        app = conn.execute(
            "SELECT * FROM applications WHERE message_id = ?", (interaction.message.id,)
        ).fetchone()
        if app is None:
            await interaction.response.send_message("Application not found.", ephemeral=True)
            return None
        if app["status"] != "pending":
            await interaction.response.send_message(
                f"Already {app['status']}.", ephemeral=True
            )
            return None
        return app

    async def _finish(self, interaction: discord.Interaction, app, status: str):
        conn.execute(
            "UPDATE applications SET status = ?, reviewer_id = ? WHERE id = ?",
            (status, interaction.user.id, app["id"]),
        )
        conn.commit()
        app = conn.execute("SELECT * FROM applications WHERE id = ?", (app["id"],)).fetchone()
        member = interaction.guild.get_member(app["user_id"])
        e = application_embed(app, member)
        e.set_footer(text=f"Application #{app['id']} · {status} by {interaction.user.display_name}")
        await interaction.message.edit(embed=e, view=None)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success,
                       custom_id="jarcord:app:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        app = await self._resolve(interaction)
        if app is None:
            return
        await interaction.response.defer()
        member = interaction.guild.get_member(app["user_id"])
        notes = []

        if member is not None:
            # link the Roblox account onto their profile
            found = await resolve_roblox(app["roblox"])
            if found:
                rid, name = found
                conn.execute(
                    """INSERT INTO profiles (user_id, roblox_name, roblox_id) VALUES (?, ?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET roblox_name = ?, roblox_id = ?""",
                    (member.id, name, rid, name, rid),
                )
                conn.commit()
                try:
                    await member.edit(nick=name)
                except discord.Forbidden:
                    notes.append("couldn't set their nickname")
            else:
                notes.append(f"Roblox user `{app['roblox']}` doesn't exist")

            role_id = get_setting("member_role_id")
            if role_id:
                role = interaction.guild.get_role(int(role_id))
                if role is None:
                    notes.append("the configured member role is gone")
                else:
                    try:
                        await member.add_roles(role)
                    except discord.Forbidden:
                        notes.append(f"couldn't assign **{role.name}** (role hierarchy)")
            try:
                await member.send(f"Your registration in **{interaction.guild.name}** was approved. Welcome aboard.")
            except discord.HTTPException:
                pass  # DMs closed — not worth reporting
        else:
            notes.append("they've left the server")

        await self._finish(interaction, app, "approved")
        if notes:
            await interaction.followup.send("Approved, but: " + "; ".join(notes) + ".", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger,
                       custom_id="jarcord:app:deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        app = await self._resolve(interaction)
        if app is None:
            return
        await interaction.response.defer()
        await self._finish(interaction, app, "denied")


class RegisterModal(discord.ui.Modal, title="Registration"):
    roblox = discord.ui.TextInput(label="Roblox username", max_length=20)
    age_group = discord.ui.TextInput(label="Age group", placeholder="e.g. 13-17, 18-24", required=False, max_length=20)
    pronouns = discord.ui.TextInput(label="Pronouns", required=False, max_length=32)
    timezone = discord.ui.TextInput(label="Time zone", placeholder="e.g. GMT, EST, UTC+2", max_length=32)
    availability = discord.ui.TextInput(
        label="Available times", style=discord.TextStyle.paragraph,
        placeholder="e.g. 20:00-24:00 weekdays, all day weekends", max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel_id = get_setting("review_channel_id")
        if not channel_id:
            await interaction.response.send_message(
                "Registration isn't set up yet — an admin needs to run `/register-setup`.", ephemeral=True
            )
            return
        channel = interaction.guild.get_channel(int(channel_id))
        if channel is None:
            await interaction.response.send_message(
                "The review channel is missing — an admin needs to re-run `/register-setup`.", ephemeral=True
            )
            return

        cur = conn.execute(
            """INSERT INTO applications (user_id, roblox, age_group, pronouns, timezone, availability)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (interaction.user.id, str(self.roblox), str(self.age_group), str(self.pronouns),
             str(self.timezone), str(self.availability)),
        )
        conn.commit()
        app = conn.execute("SELECT * FROM applications WHERE id = ?", (cur.lastrowid,)).fetchone()

        try:
            msg = await channel.send(embed=application_embed(app, interaction.user), view=ReviewView())
        except discord.Forbidden:
            await interaction.response.send_message(
                "I can't post in the review channel — ask an admin to give me access there.", ephemeral=True
            )
            return
        conn.execute("UPDATE applications SET message_id = ? WHERE id = ?", (msg.id, app["id"]))
        conn.commit()
        await interaction.response.send_message(
            "Registration submitted — staff will review it shortly.", ephemeral=True
        )


class Registration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(ReviewView())  # survives restarts

    @discord.app_commands.command(name="register", description="Apply to join the faction")
    async def register(self, interaction: discord.Interaction):
        pending = conn.execute(
            "SELECT id FROM applications WHERE user_id = ? AND status = 'pending'",
            (interaction.user.id,),
        ).fetchone()
        if pending:
            await interaction.response.send_message(
                f"You already have application #{pending['id']} awaiting review.", ephemeral=True
            )
            return
        await interaction.response.send_modal(RegisterModal())

    @commands.hybrid_command(name="register-setup", description="Set the review channel and member role")
    @commands.has_permissions(manage_guild=True)
    async def register_setup(
        self,
        ctx: commands.Context,
        review_channel: discord.TextChannel,
        member_role: discord.Role = None,
    ):
        set_setting("review_channel_id", str(review_channel.id))
        msg = f"Registrations will be reviewed in {review_channel.mention}."
        if member_role:
            set_setting("member_role_id", str(member_role.id))
            msg += f" Approved members get **{member_role.name}**."
            if member_role >= ctx.guild.me.top_role:
                msg += "\n⚠️ That role sits above mine — I won't be able to assign it. Move Jarcord higher."
        await ctx.send(msg)


async def setup(bot: commands.Bot):
    await bot.add_cog(Registration(bot))
