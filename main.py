#!/usr/bin/env python3
"""
AI Recruiter — CLI Dashboard
Usage: python main.py [command]
"""

import click
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console()


@click.group()
def cli():
    """AI Recruiter — fully automated hiring pipeline for Connor."""
    pass


# ── JOBS ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--title", prompt="Job title", help="e.g. Finance Analyst")
@click.option("--type", "job_type", default="1099", type=click.Choice(["1099", "Internship", "Part_Time"]))
@click.option("--pay", default="TBD", help="Pay range, e.g. $25-35/hr")
def add_job(title, job_type, pay):
    """Add a new job opening to Airtable."""
    import airtable_ats as ats
    description = click.prompt("Job description (1-2 sentences)")
    requirements = click.prompt("Key requirements (comma separated skills)")
    result = ats.create_job(title, job_type, description, requirements, pay)
    job_id = result["fields"]["Job_ID"]
    console.print(f"[green]✓ Job created:[/green] {title} | ID: {job_id}")


@cli.command()
def jobs():
    """List all active jobs."""
    import airtable_ats as ats
    active = ats.get_active_jobs()
    if not active:
        console.print("[yellow]No active jobs found.[/yellow]")
        return
    t = Table(title="Active Jobs", show_header=True, header_style="bold blue")
    t.add_column("Job ID", style="cyan")
    t.add_column("Title")
    t.add_column("Type")
    t.add_column("Pay")
    t.add_column("Status")
    for j in active:
        f = j["fields"]
        t.add_row(f.get("Job_ID",""), f.get("Job_Title",""), f.get("Type",""), f.get("Pay_Range",""), f.get("Status",""))
    console.print(t)


# ── CANDIDATES ────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--job-id", default="", help="Filter by job ID")
def candidates(job_id):
    """Show all qualified candidates ranked by score."""
    import airtable_ats as ats
    import candidate_scorer as scorer
    recs = ats.get_qualified_candidates(job_id)
    ranked = scorer.rank_candidates_for_job(recs, job_id or "All Roles")

    if not ranked:
        console.print("[yellow]No qualified candidates yet.[/yellow]")
        return

    t = Table(title=f"Qualified Candidates (Score ≥ 7)", show_header=True, header_style="bold green")
    t.add_column("Rank", style="bold")
    t.add_column("Name")
    t.add_column("Score", style="cyan")
    t.add_column("Recommend")
    t.add_column("Comp")
    t.add_column("Available")
    t.add_column("Calendly", style="green")
    for c in ranked:
        booked = "✓ Booked" if c["calendly_booked"] else "—"
        t.add_row(str(c["rank"]), c["name"], f"{c['score']}/10",
                  c["recommend"], c["comp"], c["availability"], booked)
    console.print(t)


@cli.command()
@click.option("--job-id", default="", help="Filter by job ID")
def digest(job_id):
    """Generate weekly candidate digest via Claude."""
    import airtable_ats as ats
    import candidate_scorer as scorer
    recs    = ats.get_qualified_candidates(job_id)
    ranked  = scorer.rank_candidates_for_job(recs, job_id or "All Roles")
    summary = scorer.generate_weekly_digest(ranked, job_id or "All Roles")
    console.print(Panel(summary, title="Weekly Digest", border_style="blue"))


# ── CALLS ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("phone")
@click.option("--name", prompt="Candidate name")
@click.option("--email", "email_addr", default="", help="Candidate email")
@click.option("--job-title", prompt="Job title")
@click.option("--job-type", default="1099", type=click.Choice(["1099", "Internship"]))
def call(phone, name, email_addr, job_title, job_type):
    """Trigger an AI screening call to a candidate right now."""
    import bland_ai
    import airtable_ats as ats
    rec = ats.create_candidate(name, email_addr, phone, job_title, source="Manual")
    result = bland_ai.trigger_outbound_call(
        phone_number=phone,
        candidate_name=name,
        job_title=job_title,
        job_type=job_type,
        candidate_email=email_addr,
        airtable_record_id=rec["id"]
    )
    console.print(f"[green]✓ Call triggered![/green] Call ID: {result.get('call_id','')}")
    console.print(f"   Status: {result.get('status','')}")


@cli.command()
def recent_calls():
    """Show recent AI screening calls."""
    import bland_ai
    calls = bland_ai.list_recent_calls(20)
    if not calls:
        console.print("[yellow]No recent calls.[/yellow]")
        return
    t = Table(title="Recent Calls", show_header=True, header_style="bold magenta")
    t.add_column("Call ID", style="cyan", max_width=20)
    t.add_column("To")
    t.add_column("Status")
    t.add_column("Duration")
    t.add_column("Created")
    for c in calls:
        t.add_row(
            c.get("call_id","")[:18],
            c.get("to",""),
            c.get("status",""),
            f"{c.get('call_length',0):.0f}s",
            c.get("created_at","")[:16]
        )
    console.print(t)


# ── OUTREACH ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--job-type-key", default="finance_analyst",
              type=click.Choice(["finance_analyst","marketing","sales","operations","software_engineer","data_analyst"]))
@click.option("--location", default="United States")
@click.option("--limit", default=25)
@click.option("--auto-email", is_flag=True, help="Automatically send outreach emails")
def source(job_type_key, location, limit, auto_email):
    """Source candidates from Apollo.io and optionally send outreach."""
    import apollo_sourcing as apollo
    import airtable_ats as ats
    import email_outreach as email

    console.print(f"[blue]Sourcing {limit} candidates for {job_type_key} in {location}...[/blue]")
    candidates = apollo.source_for_job(job_type_key, location, limit)
    console.print(f"[green]Found {len(candidates)} candidates with emails[/green]")

    for c in candidates:
        console.print(f"  {c['name']} | {c['title']} at {c['company']} | {c['email']}")

    if auto_email and click.confirm(f"\nSend outreach emails to all {len(candidates)}?"):
        job_desc = f"1099 contractor {job_type_key.replace('_', ' ')} role"
        sent = 0
        for c in candidates:
            try:
                ats.create_candidate(c["name"], c["email"], c.get("phone",""),
                                     job_type_key.replace("_"," ").title(),
                                     source="Apollo")
                email.send_outreach_email(c["name"], c["email"], job_type_key.replace("_"," ").title(), job_desc, c.get("title",""))
                sent += 1
            except Exception as ex:
                console.print(f"[red]Error sending to {c['email']}: {ex}[/red]")
        console.print(f"[green]✓ Sent {sent} outreach emails[/green]")


@cli.command()
@click.option("--job-title", prompt="Job title for sourcing strategy")
@click.option("--description", prompt="Brief job description")
def sourcing_strategy(job_title, description):
    """Use Claude to get sourcing recommendations for a role."""
    import candidate_scorer as scorer
    strategy = scorer.source_candidates_via_claude(job_title, description)
    console.print(Panel(strategy, title=f"Sourcing Strategy: {job_title}", border_style="cyan"))


# ── CALENDAR ─────────────────────────────────────────────────────────────────

@cli.command()
def upcoming():
    """Show upcoming interviews from Google Calendar."""
    from google_calendar import get_upcoming_interviews
    interviews = get_upcoming_interviews()
    if not interviews:
        console.print("[yellow]No upcoming interviews scheduled.[/yellow]")
        return
    t = Table(title="Upcoming Interviews", show_header=True, header_style="bold green")
    t.add_column("Summary")
    t.add_column("Start Time")
    t.add_column("Zoom/Location")
    for ev in interviews:
        start = ev.get("start", {}).get("dateTime", "")[:16]
        loc   = ev.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri", "—")
        t.add_row(ev.get("summary",""), start, loc)
    console.print(t)


@cli.command()
def available_slots():
    """Show your available interview slots for the next 7 days."""
    from google_calendar import get_available_slots
    slots = get_available_slots()
    console.print("\n[bold]Available Interview Slots (next 7 days):[/bold]")
    for s in slots[:10]:
        console.print(f"  • {s['display']}")


# ── SETUP ─────────────────────────────────────────────────────────────────────

@cli.command()
def setup():
    """Run first-time setup: create Calendly webhook, set up inbound call agent."""
    import calendly_integration as calendly
    import bland_ai

    console.print("[bold blue]Running first-time setup...[/bold blue]\n")

    # Calendly webhook
    try:
        result = calendly.create_webhook_subscription()
        console.print(f"[green]✓ Calendly webhook created:[/green] {result.get('resource',{}).get('uri','')}")
    except Exception as e:
        console.print(f"[yellow]Calendly webhook (may already exist): {e}[/yellow]")

    # Bland.ai inbound agent
    try:
        agent = bland_ai.create_inbound_agent()
        phone = agent.get("phone_number", "")
        agent_id = agent.get("agent", {}).get("agent_id", "")
        console.print(f"[green]✓ Inbound AI call agent created[/green]")
        console.print(f"   Phone number: [bold]{phone}[/bold]  ← Post this on job listings")
        console.print(f"   Agent ID: {agent_id}")
    except Exception as e:
        console.print(f"[yellow]Bland.ai agent setup: {e}[/yellow]")

    console.print("\n[bold green]Setup complete![/bold green]")
    console.print("Next steps:")
    console.print("  1. python main.py add-job       ← Add your first job posting")
    console.print("  2. python main.py source         ← Source candidates from Apollo")
    console.print("  3. python webhook_server.py      ← Start webhook server in background")
    console.print("  4. ngrok http 5055               ← Expose webhooks to internet")


@cli.command()
def server():
    """Start the webhook server (port 5055)."""
    import subprocess, sys
    console.print("[blue]Starting webhook server on port 5055...[/blue]")
    console.print("[yellow]Run 'ngrok http 5055' in another terminal.[/yellow]")
    subprocess.run([sys.executable, "webhook_server.py"])


@cli.command()
def dashboard():
    """Open the visual pipeline dashboard in your browser (port 5056)."""
    import subprocess, sys, webbrowser, threading, time
    def open_browser():
        time.sleep(1.2)
        webbrowser.open("http://localhost:5056")
    threading.Thread(target=open_browser, daemon=True).start()
    console.print("[blue]Dashboard starting at http://localhost:5056[/blue]")
    subprocess.run([sys.executable, "dashboard/app.py"])


@cli.command()
@click.argument("job_id")
@click.option("--boards", "-b", multiple=True,
              default=("indeed", "linkedin"),
              type=click.Choice(["indeed", "linkedin", "handshake"]))
def post_job(job_id, boards):
    """Auto-post a job to job boards using browser automation."""
    from job_poster import post_job as _post
    console.print(f"[blue]Posting {job_id} to: {', '.join(boards)}[/blue]")
    results = _post(job_id, list(boards))
    for board, r in results.items():
        if r["success"]:
            console.print(f"[green]✓ {board}[/green]")
        else:
            console.print(f"[red]✗ {board}: {r.get('error','failed')}[/red]")


@cli.command()
@click.option("--email", default="", help="Candidate email")
@click.option("--record-id", default="", help="Airtable record ID")
@click.option("--send", is_flag=True, help="Email the packet to yourself")
def prep(email, record_id, send):
    """Generate a pre-interview prep packet for a candidate."""
    from prep_packet import generate_and_print, email_prep_packet_to_connor
    if send:
        email_prep_packet_to_connor(email, record_id)
        console.print("[green]✓ Prep packet emailed to you[/green]")
    else:
        generate_and_print(email, record_id)


@cli.command()
@click.option("--email", required=True, help="Candidate email")
@click.option("--rate",  required=True, help="Pay rate e.g. '$35/hr'")
@click.option("--start", required=True, help="Start date e.g. 2026-07-01")
@click.option("--send",  is_flag=True,  help="Email offer to candidate")
def offer(email, rate, start, send):
    """Generate a 1099 contractor offer letter."""
    from offer_letter import generate_offer_letter, save_offer_letter, email_offer_letter
    import airtable_ats as ats
    cand = ats.get_candidate_by_email(email)
    if not cand:
        console.print(f"[red]Candidate not found: {email}[/red]")
        return
    name = cand["fields"].get("Name", "Candidate")
    job  = cand["fields"].get("Job_Title", "Contractor")
    if send:
        email_offer_letter(name, email, job, rate, start)
        console.print(f"[green]✓ Offer sent to {name} ({email})[/green]")
    else:
        html = generate_offer_letter(name, email, job, rate, start)
        path = save_offer_letter(html, name)
        console.print(f"[green]✓ Offer saved: {path}[/green]")
        console.print("   Add --send to email it to the candidate.")


@cli.command()
@click.argument("job_id")
@click.option("--contacts-file", default="",
              help="JSON file with [{name, email}] list. Omit to use sample.")
def blast_referrals(job_id, contacts_file):
    """Send referral ask emails to your network for a specific job."""
    import json
    from referral_engine import send_referral_blast
    if contacts_file:
        with open(contacts_file) as f:
            contacts = json.load(f)
    else:
        contacts = [{"name": "Test Contact", "email": __import__('config').YOUR_EMAIL}]
        console.print("[yellow]No contacts file given — sending test to yourself.[/yellow]")
    n = send_referral_blast(job_id, contacts)
    console.print(f"[green]✓ Sent {n} referral emails[/green]")


@cli.command()
def sequences():
    """Run due outreach sequence emails right now."""
    from email_sequences import run_due_sequences, get_sequence_stats
    n = run_due_sequences()
    stats = get_sequence_stats()
    console.print(f"[green]✓ Sent {n} sequence emails[/green]")
    console.print(f"   Active: {stats['active']} | Completed: {stats['completed']} | Replied: {stats['replied']}")


if __name__ == "__main__":
    cli()
