import pandas as pd
from fpdf import FPDF

def generate_interval_csv(interval_data):
    """
    Converts the 5-second interval JSON array into a CSV string.
    """
    df = pd.DataFrame(interval_data)
    if not df.empty and "time" in df.columns and "breakdown" in df.columns:
        df.rename(columns={"time": "Time Interval", "breakdown": "Match Breakdown"}, inplace=True)
    return df.to_csv(index=False)

def clean_text(text):
    """
    Removes/replaces special unicode characters and emojis so 
    the basic PDF generator doesn't crash during export.
    """
    if not text: 
        return ""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def generate_pdf_report(data, filename="Video"):
    """
    Generates a highly detailed, multi-page PDF report mirroring the UI.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- Title ---
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=clean_text(f"BJJ Match Analysis Report - {filename}"), ln=True, align='C')
    pdf.ln(5)
    
    # --- 1. Overall Performance ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="1. Overall Performance", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, txt=clean_text(f"Score: {data.get('overall_score', 'N/A')} - {data.get('performance_label', '')}"), ln=True)
    
    grades = data.get('grades', {})
    pdf.cell(0, 8, txt=clean_text(f"Grades -> Defense: {grades.get('defense','N/A')} | Offense: {grades.get('offense','N/A')} | Control: {grades.get('control','N/A')}"), ln=True)
    pdf.ln(5)

    # --- 2. Playstyle Comparison ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="2. Playstyle Comparison", ln=True)
    pdf.set_font("Arial", '', 11)
    
    u_stats = data.get('user_stats', {})
    o_stats = data.get('opponent_stats', {})
    
    pdf.cell(0, 6, txt=clean_text(f"Your Stats: Offense {u_stats.get('offense',0)}% | Defense {u_stats.get('defense',0)}% | Guard {u_stats.get('guard',0)}% | Passing {u_stats.get('passing',0)}%"), ln=True)
    pdf.cell(0, 6, txt=clean_text(f"Opponent Stats: Offense {o_stats.get('offense',0)}% | Defense {o_stats.get('defense',0)}% | Guard {o_stats.get('guard',0)}% | Passing {o_stats.get('passing',0)}%"), ln=True)
    pdf.ln(5)

    # --- 3. Interval Breakdown ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="3. 5-Second Interval Breakdown", ln=True)
    pdf.set_font("Arial", '', 11)
    for interval in data.get('interval_breakdown', []):
        t_val = interval.get('time', 'N/A')
        b_val = interval.get('breakdown', 'N/A')
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 6, txt=clean_text(f"[{t_val}]"), ln=True)
        pdf.set_font("Arial", '', 11)
        pdf.multi_cell(0, 6, txt=clean_text(b_val))
        pdf.ln(2)
    pdf.ln(3)

    # --- 4. Strengths & Weaknesses ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="4. Strengths & Weaknesses", ln=True)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 6, txt="Your Strengths:", ln=True)
    pdf.set_font("Arial", '', 11)
    for s in data.get('user_strengths', []): pdf.multi_cell(0, 6, txt=clean_text(f"- {s}"))
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 6, txt="Your Weaknesses:", ln=True)
    pdf.set_font("Arial", '', 11)
    for w in data.get('user_weaknesses', []): pdf.multi_cell(0, 6, txt=clean_text(f"- {w}"))
    pdf.ln(2)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 6, txt="Opponent Strengths:", ln=True)
    pdf.set_font("Arial", '', 11)
    for s in data.get('opponent_strengths', []): pdf.multi_cell(0, 6, txt=clean_text(f"- {s}"))

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 6, txt="Opponent Weaknesses:", ln=True)
    pdf.set_font("Arial", '', 11)
    for w in data.get('opponent_weaknesses', []): pdf.multi_cell(0, 6, txt=clean_text(f"- {w}"))
    pdf.ln(5)

    # --- 5. Missed Opportunities ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="5. Opportunities Missed", ln=True)
    pdf.set_font("Arial", '', 11)
    for opp in data.get('missed_opportunities', []):
        t = opp.get('time', '')
        cat = opp.get('category', '')
        title = opp.get('title', '')
        desc = opp.get('description', '')
        pdf.multi_cell(0, 6, txt=clean_text(f"[{t}] {cat} - {title}: {desc}"))
    pdf.ln(5)

    # --- 6. Key Moments ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="6. Key Moments", ln=True)
    pdf.set_font("Arial", '', 11)
    for km in data.get('key_moments', []):
        t = km.get('time', '')
        title = km.get('title', '')
        desc = km.get('description', '')
        pdf.multi_cell(0, 6, txt=clean_text(f"[{t}] {title}: {desc}"))
    pdf.ln(5)

    # --- 7. Coach Insights ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="7. Coach Insights", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, txt=clean_text(data.get('coach_notes', '')))

    return pdf.output(dest='S').encode('latin1')