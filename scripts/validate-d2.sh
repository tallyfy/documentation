#!/bin/bash

# D2 Diagram Validation Script
# Validates all D2 diagrams in documentation before pushing to avoid build failures

echo "🔍 Validating D2 diagrams in documentation..."

# Check if d2 is installed
if ! command -v d2 &> /dev/null; then
    echo "❌ D2 is not installed. Install it with: brew install d2"
    exit 1
fi

# Counter for errors
error_count=0
checked_count=0
temp_file="/tmp/d2_validate_$$.d2"
output_file="/tmp/d2_validate_$$.svg"

# Clean up on exit
trap "rm -f $temp_file $output_file" EXIT

# Find all MDX files with D2 diagrams
for file in $(grep -r '```d2' src/content/docs --include='*.mdx' -l); do
    echo "Checking: $file"
    checked_count=$((checked_count + 1))
    
    # Extract each D2 block from the file
    block_num=0
    awk '/^```d2$/,/^```$/' "$file" | while IFS= read -r line; do
        if [[ "$line" == '```d2' ]]; then
            block_num=$((block_num + 1))
            > "$temp_file"  # Clear temp file
        elif [[ "$line" == '```' ]]; then
            if [ -s "$temp_file" ]; then
                # Try to compile the D2 diagram
                if ! d2 "$temp_file" "$output_file" 2>/dev/null; then
                    echo "  ❌ D2 syntax error in block $block_num"
                    # Show the actual error
                    echo "  Error details:"
                    d2 "$temp_file" "$output_file" 2>&1 | head -5 | sed 's/^/    /'
                    error_count=$((error_count + 1))
                else
                    echo "  ✅ Block $block_num valid"
                fi
            fi
        else
            echo "$line" >> "$temp_file"
        fi
    done
done

# Summary
echo ""
echo "📊 Validation Summary:"
echo "  Checked: $checked_count files"
echo "  Errors: $error_count"

if [ $error_count -gt 0 ]; then
    echo "❌ D2 validation failed! Fix the errors above before pushing."
    exit 1
else
    echo "✅ All D2 diagrams are valid!"
    exit 0
fi