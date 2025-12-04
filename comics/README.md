# Documentation Comics

Simple 2-panel comic strips for high-value documentation articles. Each comic emphasizes a pain point (Before) and solution (After with Tallyfy).

## Workflow

### Phase 1: Generate Comics
1. Copy prompt from `prompts/XX-name.prompt`
2. Paste into Nano Banana Pro
3. Generate image
4. Save as `generated/XX-name.png`

### Phase 2: Process & Integrate
Drag the saved PNG into the Claude Code terminal session. Claude will:
- Upload to R2 CDN
- Generate AI captions
- Update asset inventory
- Insert into the correct article
- Verify placement

## Directory Structure

```
comics/
├── prompts/           # Nano Banana Pro prompts
│   └── 01-forgetting-curve.prompt
├── generated/         # Save generated PNGs here
└── integration/       # Tracking metadata
```

## Comic Specifications

- **Dimensions**: 1200x600 pixels
- **Panels**: 2 (Before/After)
- **Style**: Bold cartoon, thick outlines
- **Brand color**: #01803d (Tallyfy green)
- **Dual-mode**: Works on light AND dark backgrounds
