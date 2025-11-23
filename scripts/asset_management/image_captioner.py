#!/usr/bin/env python3
"""
AI-powered image caption generator for documentation assets.

Uses Claude Code's native capabilities to generate three types of captions:
1. Alt text - Concise, accessibility-focused (50-150 chars)
2. Descriptive - Detailed explanation (2-4 sentences)
3. SEO - Keyword-optimized for search engines

Note: This script is designed to be called BY Claude Code itself,
utilizing its native Read tool for vision analysis.
"""

import re
import time
import subprocess
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse


class ImageCaptioner:
    """Generate AI captions for documentation images using Claude Code."""

    # Prompts for different caption types
    PROMPTS = {
        'alt_text': """Analyze this screenshot and generate a concise alt text description.

Requirements:
- 1-2 sentences maximum (50-150 characters)
- Focus on what the image shows, not how it looks
- No phrases like "screenshot of" or "image showing"
- Directly describe the interface elements and their purpose
- Suitable for screen readers

Example good alt texts:
- "Task assignment interface with role and user selection dropdown menus"
- "Process tracker dashboard showing active workflow status columns"
- "Template editor with step configuration panel and automation rules"

Return ONLY the alt text, nothing else.""",

        'descriptive': """Analyze this screenshot and generate a detailed descriptive caption.

Requirements:
- 2-4 complete sentences
- Describe specific UI elements visible in the screenshot
- Explain what functionality is being demonstrated
- Include key visual details that help understand the interface
- Mention Tallyfy product features shown
- Use natural, professional language

Example good descriptive captions:
- "Tallyfy task assignment screen showing dropdown options to assign by specific user, role, or group. The interface displays deadline settings, priority levels, and an optional notification toggle. Assignment can be made to multiple users simultaneously with role-based dynamic routing."

Return ONLY the descriptive caption, nothing else.""",

        'seo': """Analyze this screenshot and generate SEO-optimized keywords and phrases.

Requirements:
- Extract feature names, UI elements, and user actions shown
- Include product name "Tallyfy" naturally
- Use keywords that users might search for
- Focus on functionality and features demonstrated
- Natural phrasing (not just keyword stuffing)
- 15-30 words total

Example good SEO captions:
- "assign tasks Tallyfy role-based assignment user assignment group assignment workflow management task routing deadline setting priority levels"
- "Tallyfy template editor workflow automation configuration step sequencing team access control notification rules approval workflow"

Return ONLY the SEO keywords/phrases, nothing else."""
    }

    def __init__(self, rate_limit_delay: float = 2.0):
        """
        Initialize caption generator.

        Args:
            rate_limit_delay: Seconds to wait between API calls
        """
        self.rate_limit_delay = rate_limit_delay
        self.last_call_time = 0.0

    def generate_captions(
        self,
        image_path: str | Path,
        caption_types: Optional[list[str]] = None
    ) -> Dict[str, str]:
        """
        Generate all caption types for an image.

        Args:
            image_path: Path to image file or URL
            caption_types: List of caption types to generate
                          (default: ['alt_text', 'descriptive', 'seo'])

        Returns:
            dict: Caption results with keys matching caption_types
                 {'alt_text': '...', 'descriptive': '...', 'seo': '...'}
                 If generation fails, value will be empty string

        Note: This method is designed to be CALLED BY Claude Code.
        It returns a template that should be filled in by the AI.
        """
        if caption_types is None:
            caption_types = ['alt_text', 'descriptive', 'seo']

        # Validate image path
        image_str = str(image_path)
        is_url = image_str.startswith('http')

        if not is_url:
            path = Path(image_path)
            if not path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")
            if path.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
                raise ValueError(f"Unsupported image format: {path.suffix}")

        # Generate caption for each requested type
        results = {}
        for caption_type in caption_types:
            if caption_type not in self.PROMPTS:
                raise ValueError(f"Unknown caption type: {caption_type}")

            # Rate limiting
            self._rate_limit()

            # Generate caption
            caption = self._generate_single_caption(image_path, caption_type)
            results[caption_type] = caption

        return results

    def _generate_single_caption(self, image_path: str | Path, caption_type: str) -> str:
        """
        Generate a single caption using Claude Code.

        This is a PLACEHOLDER method that should be called within a Claude Code session.
        When running this script via Claude Code, it can use the Read tool on images.

        Args:
            image_path: Path or URL to image
            caption_type: Type of caption ('alt_text', 'descriptive', 'seo')

        Returns:
            str: Generated caption text
        """
        prompt = self.PROMPTS[caption_type]

        # In a Claude Code execution context, this would use the Read tool
        # For now, return a template that indicates manual processing needed
        return f"[CAPTION NEEDED: {caption_type} for {Path(image_path).name}]"

    def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time

        if time_since_last_call < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last_call)

        self.last_call_time = time.time()

    @staticmethod
    def validate_caption(caption: str, caption_type: str) -> tuple[bool, Optional[str]]:
        """
        Validate that a caption meets requirements.

        Args:
            caption: Caption text to validate
            caption_type: Type of caption being validated

        Returns:
            tuple: (is_valid, error_message)
        """
        if not caption or not caption.strip():
            return (False, "Caption is empty")

        caption = caption.strip()

        if caption_type == 'alt_text':
            # Alt text should be 50-150 characters
            if len(caption) < 30:
                return (False, f"Alt text too short ({len(caption)} chars, minimum 30)")
            if len(caption) > 200:
                return (False, f"Alt text too long ({len(caption)} chars, maximum 200)")

            # Should not contain phrases like "screenshot of"
            bad_phrases = ['screenshot of', 'image of', 'picture of', 'photo of']
            if any(phrase in caption.lower() for phrase in bad_phrases):
                return (False, f"Contains discouraged phrase: {bad_phrases}")

        elif caption_type == 'descriptive':
            # Should be 2-4 sentences (check for periods)
            sentences = [s for s in caption.split('.') if s.strip()]
            if len(sentences) < 2:
                return (False, f"Too few sentences ({len(sentences)}, minimum 2)")
            if len(sentences) > 5:
                return (False, f"Too many sentences ({len(sentences)}, maximum 5)")

            # Should mention Tallyfy
            if 'tallyfy' not in caption.lower():
                return (False, "Should mention 'Tallyfy' product name")

        elif caption_type == 'seo':
            # Should have reasonable word count
            words = caption.split()
            if len(words) < 10:
                return (False, f"Too few keywords ({len(words)}, minimum 10)")
            if len(words) > 40:
                return (False, f"Too many keywords ({len(words)}, maximum 40)")

        return (True, None)


def generate_captions_via_claude(
    image_path: str | Path,
    output_format: str = 'dict'
) -> Dict[str, str]:
    """
    Wrapper function for Claude Code to call for caption generation.

    This function is the integration point - Claude Code should:
    1. Read the image using the Read tool
    2. Apply each prompt from ImageCaptioner.PROMPTS
    3. Return the generated captions

    Args:
        image_path: Path or URL to image
        output_format: 'dict' or 'json'

    Returns:
        dict: Generated captions
    """
    captioner = ImageCaptioner()

    # This will return placeholder text - Claude Code should replace with actual analysis
    captions = captioner.generate_captions(image_path)

    return captions


# CLI interface for manual testing
if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description='Generate AI captions for documentation images (via Claude Code)'
    )
    parser.add_argument('image', help='Image file path or URL')
    parser.add_argument(
        '--types',
        nargs='+',
        choices=['alt_text', 'descriptive', 'seo', 'all'],
        default=['all'],
        help='Caption types to generate'
    )
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    # Determine caption types
    if 'all' in args.types:
        caption_types = ['alt_text', 'descriptive', 'seo']
    else:
        caption_types = args.types

    # Generate captions
    captioner = ImageCaptioner()

    print(f"📷 Analyzing image: {args.image}")
    print(f"🎯 Generating: {', '.join(caption_types)}\n")

    print("=" * 60)
    print("⚠️  IMPORTANT: Caption generation requires Claude Code execution")
    print("=" * 60)
    print()
    print("This script provides the framework and prompts for caption generation.")
    print("To actually generate captions, call this from within Claude Code:")
    print()
    print("  claude -p \"Generate captions for image.png using image_captioner.py\"")
    print()
    print("The prompts that will be used:")
    print()

    for caption_type in caption_types:
        print(f"\n--- {caption_type.upper().replace('_', ' ')} PROMPT ---")
        print(ImageCaptioner.PROMPTS[caption_type])

    # Show placeholder result
    result = captioner.generate_captions(args.image, caption_types)

    print("\n" + "=" * 60)
    print("PLACEHOLDER RESULT (to be filled by Claude Code):")
    print("=" * 60)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for caption_type, caption in result.items():
            print(f"\n{caption_type}:")
            print(f"  {caption}")
