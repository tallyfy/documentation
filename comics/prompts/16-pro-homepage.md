# Pro Homepage Illustration Prompt

## Target Article
- **Path**: `/documentation/src/content/docs/pro/index.mdx`
- **Title**: Introduction
- **Theme**: Tallyfy Pro product overview - Document → Launch → Track workflow

---

=== ARTICLE SUMMARY ===
Tallyfy Pro transforms business processes into self-driving workflows. The core value proposition:
1. DOCUMENT: Capture processes in minutes (like recipes) using AI or document import
2. LAUNCH: Turn templates into active processes with one click - they run themselves
3. TRACK: Real-time visibility into who's doing what, with automatic reminders

The article emphasizes saving 2 hours per employee daily by eliminating status meetings and follow-ups.
=== END ARTICLE SUMMARY ===

=== IMAGE GENERATION REQUEST ===

Create a sophisticated, premium editorial illustration in the style of Harvard Business Review or The Economist that captures the essence of Tallyfy's core workflow: creating a template, launching multiple processes, and tracking each one.

BRAND COLORS - USE THESE EXACTLY:
- Dark Green (#01803d): The master template blueprint - represents authority and the source of truth
- Green (#3fb65b): The running processes - represents success, active workflows, positive progress
- Orange (#f26523): ONLY for the X in the solution indicator, nowhere else
- Dark Grey (#414042): Text labels, outlines, structural elements
- White (#FFFFFF): MANDATORY pure white background - no grey tints

MAIN ILLUSTRATION - TEMPLATE TO PROCESS FLOW (85% of image):

A clean, elegant visualization showing the one-to-many relationship between a template and processes:

LEFT SIDE - THE MASTER TEMPLATE:
- A single, prominent blueprint-style document in dark green (#01803d)
- Clean rectangular shape with visible step indicators (3-4 horizontal lines suggesting workflow steps)
- Subtle glow or emphasis indicating this is the authoritative source
- Label: "Template" in Inter Bold

CENTER - FLOWING TRANSFORMATION:
- Elegant flowing lines or ribbons in green (#3fb65b) emanating from the template
- Lines branch outward like a river delta or tree branches
- Shows the multiplication effect - one template becomes many processes
- Visual flow moving left to right

RIGHT SIDE - MULTIPLE RUNNING PROCESSES:
- 3-4 smaller green (#3fb65b) process cards/documents arranged vertically
- Each shows a progress indicator (partially filled bars or checkmarks)
- Each at a different completion stage (25%, 50%, 75%, complete)
- Small person silhouettes or avatars next to each indicating assignments
- Labels like "Client A", "Client B", "Client C" in Inter Medium
- Subtle green glow indicating these are "live" and active

COMPOSITION:
- Single template on the left (focal point, slightly larger)
- Flow lines in the middle (showing transformation)
- Multiple processes on the right (showing scale)
- Visual flow naturally moves left to right
- Plenty of white space around elements
- Bottom-right corner reserved for minimal solution indicator

SOLUTION INDICATOR (Bottom-right corner, 15%):
- Small orange (#f26523) X icon → thin dark grey arrow → PURE WHITE EMPTY SPACE
- CRITICAL: NO grey rectangle, NO placeholder box, NO checkmarks, NO background
- The logo will be added programmatically AFTER image generation
- Just the orange X, a thin arrow, then WHITE SPACE - nothing else
- AI generators often add grey placeholder boxes - this MUST be prevented
- Must be minimal and elegant, NOT attention-grabbing

TYPOGRAPHY:
- Inter font family
- Bold for "Template" label
- SemiBold for process names
- Medium for progress labels
- All text in dark grey (#414042)

VISUAL STYLE:
Include:
- Premium editorial illustration aesthetic (HBR/Economist/McKinsey)
- Clean, crisp vector-like edges throughout
- Sophisticated color palette with intentional restraint
- Simple, uncluttered composition
- Geometric shapes with clean lines

Avoid:
- Cartoonish elements or characters
- Gradients, drop shadows, 3D glossy effects
- Grey or cream background tints
- Clip art style or generic stock illustration feel
- Complex or busy scenes
- Too many visual elements - keep it simple

EMOTIONAL IMPACT:
- Immediate understanding of "one template creates many processes"
- Feeling of efficiency and scale
- Clarity about the workflow: create once, use many times
- Professional confidence - this is a system that works

DIMENSIONS: 1200x600 JPEG
BACKGROUND: Pure white #FFFFFF - absolutely critical requirement

---

## Next Steps After Generation

1. Generate the image using Nano Banana Pro or similar AI image generator
2. Save the raw image to `/comics/generated/16-pro-homepage.jpeg`
3. Claude will run the logo compositor
4. Upload to R2 at `illustrations/pro-homepage.jpeg`
5. Insert into the Pro homepage article after the first paragraph
