
import sys
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.enum.shapes import MSO_SHAPE
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-pptx"])
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.enum.shapes import MSO_SHAPE

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# Color Palette: Astra Dark Nebula
BG_COLOR = RGBColor(11, 15, 25)        # Deep space slate #0B0F19
CARD_BG = RGBColor(22, 30, 49)        # Card container #161E31
ACCENT_CYAN = RGBColor(0, 229, 255)   # Astra Cyan #00E5FF
ACCENT_PURPLE = RGBColor(168, 85, 247)# Astra Purple #A855F7
ACCENT_AMBER = RGBColor(245, 158, 11) # Metric highlight #F59E0B
TEXT_LIGHT = RGBColor(241, 245, 249)  # Slate 100 #F1F5F9
TEXT_MUTED = RGBColor(148, 163, 184)  # Slate 400 #94A3B8

def apply_slide_bg(slide):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = BG_COLOR

def add_header(slide, title_text, category_text="GPT-6 ASTRA ARCHITECTURE DECK"):
    # Category tag
    cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.4))
    tf_cat = cat_box.text_frame
    tf_cat.word_wrap = True
    p_cat = tf_cat.paragraphs[0]
    p_cat.text = category_text.upper()
    p_cat.font.size = Pt(11)
    p_cat.font.bold = True
    p_cat.font.color.rgb = ACCENT_CYAN
    
    # Title
    t_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.85), Inches(11.7), Inches(0.8))
    tf = t_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = TEXT_LIGHT

# Slide 1: Title Slide
blank_layout = prs.slide_layouts[6]
slide1 = prs.slides.add_slide(blank_layout)
apply_slide_bg(slide1)

# Title container shape
title_card = slide1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.5), Inches(1.5), Inches(10.333), Inches(4.5))
title_card.fill.solid()
title_card.fill.fore_color.rgb = CARD_BG
title_card.line.color.rgb = ACCENT_CYAN
title_card.line.width = Pt(1.5)

tb = slide1.shapes.add_textbox(Inches(2.0), Inches(2.0), Inches(9.333), Inches(3.5))
tf = tb.text_frame
tf.word_wrap = True

p0 = tf.paragraphs[0]
p0.text = "NEXT-GENERATION FRONTIER INTELLIGENCE"
p0.font.size = Pt(13)
p0.font.bold = True
p0.font.color.rgb = ACCENT_CYAN

p1 = tf.add_paragraph()
p1.text = "ChatGPT-6 Astra"
p1.font.size = Pt(44)
p1.font.bold = True
p1.font.color.rgb = TEXT_LIGHT
p1.space_before = Pt(10)

p2 = tf.add_paragraph()
p2.text = "Autonomous Multi-Agent Synthesis, Real-time World-State Grounding & Quantum-Ready Inference"
p2.font.size = Pt(16)
p2.font.color.rgb = TEXT_MUTED
p2.space_before = Pt(12)

# Slide 2: Core Pillars & Architecture
slide2 = prs.slides.add_slide(blank_layout)
apply_slide_bg(slide2)
add_header(slide2, "ChatGPT-6 Astra: Core Architecture Pillars")

cards_data = [
    ("1. Astra Neural Fabric", "100M+ Sparse MoE routing with ultra-low latency sub-millisecond reasoning layers.", ACCENT_CYAN),
    ("2. Realtime Grounding", "Continuous web-environment state sync with active verification pipelines.", ACCENT_PURPLE),
    ("3. Zero-Loss Reasoning", "MCTS-driven test-time compute scaling ensuring provable logical consistency.", ACCENT_AMBER)
]

for i, (title, desc, accent) in enumerate(cards_data):
    left = Inches(0.8 + i * 4.0)
    card = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, Inches(2.0), Inches(3.7), Inches(4.6))
    card.fill.solid()
    card.fill.fore_color.rgb = CARD_BG
    card.line.color.rgb = accent
    card.line.width = Pt(1.5)
    
    tb = slide2.shapes.add_textbox(left + Inches(0.3), Inches(2.3), Inches(3.1), Inches(4.0))
    tf = tb.text_frame
    tf.word_wrap = True
    
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = accent
    
    p_desc = tf.add_paragraph()
    p_desc.text = desc
    p_desc.font.size = Pt(14)
    p_desc.font.color.rgb = TEXT_LIGHT
    p_desc.space_before = Pt(14)

# Slide 3: Technical Specifications & Diagrams
slide3 = prs.slides.add_slide(blank_layout)
apply_slide_bg(slide3)
add_header(slide3, "Performance Benchmarks & System Flow")

# Left flow diagram box
flow_box = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(2.0), Inches(6.0), Inches(4.6))
flow_box.fill.solid()
flow_box.fill.fore_color.rgb = CARD_BG
flow_box.line.color.rgb = ACCENT_PURPLE

tb_flow = slide3.shapes.add_textbox(Inches(1.1), Inches(2.3), Inches(5.4), Inches(4.0))
tf_flow = tb_flow.text_frame
tf_flow.word_wrap = True
p = tf_flow.paragraphs[0]
p.text = "End-to-End System Pipeline"
p.font.size = Pt(18)
p.font.bold = True
p.font.color.rgb = ACCENT_PURPLE

steps = [
    "[Input Vector] -> Multimodal Tokenizer (Vision/Text/Audio)",
    "[Routing Layer] -> Dynamic MoE Gate (Top-k Dispatch)",
    "[Inference Engine] -> Speculative MCTS Search Tree",
    "[Execution Core] -> Sandboxed Tool & Browser Execution",
    "[Output Synthesis] -> Hallucination Filter & Final Response"
]
for s in steps:
    p_s = tf_flow.add_paragraph()
    p_s.text = s
    p_s.font.size = Pt(12)
    p_s.font.color.rgb = TEXT_LIGHT
    p_s.space_before = Pt(10)

# Right metrics box
metrics_box = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7.1), Inches(2.0), Inches(5.4), Inches(4.6))
metrics_box.fill.solid()
metrics_box.fill.fore_color.rgb = CARD_BG
metrics_box.line.color.rgb = ACCENT_CYAN

tb_met = slide3.shapes.add_textbox(Inches(7.4), Inches(2.3), Inches(4.8), Inches(4.0))
tf_met = tb_met.text_frame
tf_met.word_wrap = True
p_m = tf_met.paragraphs[0]
p_m.text = "Astra Key Performance Indicators"
p_m.font.size = Pt(18)
p_m.font.bold = True
p_m.font.color.rgb = ACCENT_CYAN

metrics = [
    ("Context Window", "10,000,000 Tokens (100% Recall)"),
    ("Inference Speed", "340 Tokens / Sec (Ultra Fast)"),
    ("Reasoning Accuracy", "98.4% on FrontierMath & GPQA"),
    ("Tool Autonomy", "99.1% Multi-step Agent Success")
]
for label, val in metrics:
    p_l = tf_met.add_paragraph()
    p_l.text = f"• {label}: {val}"
    p_l.font.size = Pt(13)
    p_l.font.color.rgb = TEXT_LIGHT
    p_l.space_before = Pt(12)

prs.save("chatgpt6_astra_presentation.pptx")
print("Presentation generated successfully: chatgpt6_astra_presentation.pptx")
