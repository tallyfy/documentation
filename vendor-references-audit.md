# MDX Files Referencing External Vendors and Services

## Summary
This audit identifies MDX documentation files that reference external vendors, third-party services, or technologies that may need regular updates due to:
- Service API changes
- Feature updates
- Pricing changes
- Deprecations or sunset dates
- Version-specific references

---

## 1. AI/ML Services

### OpenAI/ChatGPT
- `/src/content/docs/pro/integrations/computer-ai-agents/vendors/openai-chatgpt-agent.mdx`
- `/src/content/docs/pro/integrations/mcp-server/openai-chatgpt/index.mdx`
- `/src/content/docs/pro/integrations/computer-ai-agents/index.mdx`
- `/src/content/docs/pro/integrations/computer-ai-agents/rpa-vs-computer-use-agents.mdx`

### Claude/Anthropic
- `/src/content/docs/pro/integrations/computer-ai-agents/vendors/claude-computer-use.mdx`
- `/src/content/docs/pro/integrations/mcp-server/claude-anthropic/index.mdx`
- `/src/content/docs/pro/integrations/mcp-server/index.mdx`

### Other AI Agents
- `/src/content/docs/pro/integrations/computer-ai-agents/vendors/manus.mdx`
- `/src/content/docs/pro/integrations/computer-ai-agents/vendors/twin.mdx`
- `/src/content/docs/pro/integrations/computer-ai-agents/vendors/skyvern.mdx`
- `/src/content/docs/pro/integrations/computer-ai-agents/local-computer-use-agents.mdx`

---

## 2. Analytics & BI Platforms

### Tableau
- `/src/content/docs/pro/integrations/analytics/tableau/how-can-i-connect-tableau-to-my-tallyfy-data.mdx`
- `/src/content/docs/pro/integrations/analytics/tableau/sample-tableau-visualizations.mdx`
- `/src/content/docs/pro/integrations/analytics/tableau/how-to-troubleshoot-data-connection-issues-in-tallyfy.mdx`
- `/src/content/docs/pro/integrations/analytics/tableau/share-workbook-without-data.mdx`
- `/src/content/docs/pro/integrations/analytics/tableau/index.mdx`

### Power BI
- `/src/content/docs/pro/integrations/analytics/powerbi/how-to-analyze-tallyfy-workflows-with-power-bi.mdx`
- `/src/content/docs/pro/integrations/analytics/powerbi/index.mdx`

### Sigma Computing
- `/src/content/docs/pro/integrations/analytics/sigma/index.mdx`
- `/src/content/docs/pro/integrations/analytics/sigma/current-connection-limitations.mdx`
- `/src/content/docs/pro/integrations/analytics/sigma/alternatives-for-tallyfy-analytics.mdx`

### Google Analytics
- `/src/content/docs/pro/integrations/analytics/how-to-set-up-google-analytics-integration-on-tallyfy.mdx`

---

## 3. Cloud Providers & Services

### Microsoft Azure
- `/src/content/docs/pro/integrations/azure-translation/how-to-set-up-azure-cognitive-ai-integration.mdx`
- `/src/content/docs/pro/integrations/azure-translation/how-to-use-content-translation.mdx`
- `/src/content/docs/pro/integrations/azure-translation/global-workplace-language-requirements.mdx`
- `/src/content/docs/pro/integrations/azure-translation/index.mdx`
- `/src/content/docs/pro/integrations/authentication/how-to-integrate-azure-ad-samlsso-with-tallyfy.mdx`

### AWS Services
- `/src/content/docs/pro/integrations/analytics/sigma/current-connection-limitations.mdx` (AWS Athena, Redshift, S3)
- `/src/content/docs/pro/integrations/analytics/sigma/alternatives-for-tallyfy-analytics.mdx` (QuickSight)

### Google Services
- `/src/content/docs/pro/integrations/authentication/how-to-integrate-google-suite-samlsso-with-tallyfy.mdx`
- `/src/content/docs/pro/integrations/email/how-can-i-manage-my-tasks-with-tallyfys-gmail-add-on.mdx`

---

## 4. Authentication Providers

### SSO/SAML Providers
- `/src/content/docs/pro/integrations/authentication/how-to-integrate-okta-samlsso-with-tallyfy.mdx`
- `/src/content/docs/pro/integrations/authentication/how-to-integrate-onelogin-samlsso-with-tallyfy.mdx`
- `/src/content/docs/pro/integrations/authentication/index.mdx`
- `/src/content/docs/pro/integrations/mcp-server/sso-authentication/index.mdx`

---

## 5. Middleware & Automation Platforms

### Zapier
- `/src/content/docs/pro/integrations/middleware/zapier/index.mdx`
- `/src/content/docs/pro/integrations/middleware/zapier/how-to-connect-your-tallyfy-account-to-zapier.mdx`
- `/src/content/docs/pro/integrations/middleware/zapier/how-to-automate-monthly-process-launch-with-zapier.mdx`
- `/src/content/docs/pro/integrations/middleware/zapier/how-to-customize-your-tallyfy-zap-for-launch-process.mdx`
- `/src/content/docs/pro/integrations/middleware/zapier/how-to-automate-tasks-in-tallyfy-using-zaps.mdx`
- `/src/content/docs/pro/integrations/middleware/zapier/zapier-integration-troubleshooting.mdx`
- `/src/content/docs/pro/integrations/middleware/zapier/how-can-i-improve-task-management-with-tallyfy.mdx`

### Microsoft Power Automate
- `/src/content/docs/pro/integrations/middleware/power-automate/index.mdx`
- `/src/content/docs/pro/integrations/middleware/power-automate/how-can-i-integrate-tallyfy-with-microsoft-power-automate.mdx`
- `/src/content/docs/pro/integrations/middleware/power-automate/understanding-power-automate-basics.mdx`
- `/src/content/docs/pro/integrations/middleware/power-automate/creating-your-first-flow-in-power-automate.mdx`
- `/src/content/docs/pro/integrations/middleware/power-automate/building-approval-workflows-with-power-automate.mdx`
- `/src/content/docs/pro/integrations/middleware/power-automate/integrating-power-automate-approvals-with-microsoft-teams.mdx`
- `/src/content/docs/pro/integrations/middleware/power-automate/using-ai-builder-in-power-automate.mdx`
- `/src/content/docs/pro/integrations/middleware/power-automate/introduction-to-rpa-with-power-automate.mdx`
- (10+ more Power Automate files)

### n8n
- `/src/content/docs/pro/integrations/middleware/n8n/index.mdx`
- `/src/content/docs/pro/integrations/middleware/n8n/connecting-n8n-to-tallyfy.mdx`
- `/src/content/docs/pro/integrations/middleware/n8n/common-n8n-workflow-examples.mdx`
- `/src/content/docs/pro/integrations/middleware/n8n/n8n-vs-other-middleware-platforms.mdx`

### Workato
- `/src/content/docs/pro/integrations/middleware/workato/index.mdx`
- `/src/content/docs/pro/integrations/middleware/workato/how-to-complete-tallyfy-tasks-from-workato.mdx`
- `/src/content/docs/pro/integrations/middleware/workato/how-to-launch-tallyfy-processes-from-workato.mdx`

---

## 6. Communication Platforms

### Slack
- `/src/content/docs/pro/integrations/slack/index.mdx`

### Microsoft Teams/Copilot
- `/src/content/docs/pro/integrations/mcp-server/microsoft-copilot-studio/index.mdx`
- `/src/content/docs/pro/integrations/middleware/power-automate/integrating-power-automate-approvals-with-microsoft-teams.mdx`

---

## 7. Business Systems

### EOS (Entrepreneurial Operating System)
- `/src/content/docs/pro/integrations/business-systems/eos-integration.mdx`
- `/src/content/docs/pro/integrations/business-systems/index.mdx`

---

## 8. API Documentation Tools

### Postman
- `/src/content/docs/pro/integrations/open-api/api-clients/postman/index.mdx`
- `/src/content/docs/pro/integrations/open-api/api-clients/postman/authentication-setup.mdx`
- `/src/content/docs/pro/integrations/open-api/api-clients/postman/troubleshooting.mdx`
- `/src/content/docs/pro/integrations/open-api/api-clients/postman/task-operations.mdx`
- `/src/content/docs/pro/integrations/open-api/api-clients/postman/templates-processes.mdx`
- `/src/content/docs/pro/integrations/open-api/api-clients/postman/collection-organization.mdx`
- `/src/content/docs/pro/integrations/open-api/api-clients/postman/advanced-patterns.mdx`

---

## 9. Email & Document Services

### Email Services
- `/src/content/docs/pro/integrations/email/how-can-i-manage-my-tasks-with-tallyfys-gmail-add-on.mdx`
- `/src/content/docs/pro/integrations/email/how-to-set-up-custom-smtp-in-tallyfy.mdx`

### Document Signing
- `/src/content/docs/pro/documenting/documents/how-can-i-automate-document-signing-with-tallyfy.mdx`

---

## 10. Browser-Specific Documentation

### Browser Cache/Troubleshooting
- `/src/content/docs/pro/miscellaneous/troubleshooting/clear-cache-chrome.mdx`
- `/src/content/docs/pro/miscellaneous/troubleshooting/clear-cache-firefox.mdx`
- `/src/content/docs/pro/miscellaneous/troubleshooting/clear-cache-safari.mdx`
- `/src/content/docs/pro/miscellaneous/troubleshooting/clear-cache-edge.mdx`

---

## 11. Data Warehouses

### Snowflake/Redshift
- `/src/content/docs/pro/integrations/analytics/sigma/current-connection-limitations.mdx`
- `/src/content/docs/pro/integrations/analytics/sigma/alternatives-for-tallyfy-analytics.mdx`

---

## 12. Model Context Protocol (MCP)

### MCP Server Integrations
- `/src/content/docs/pro/integrations/mcp-server/index.mdx`
- `/src/content/docs/pro/integrations/mcp-server/claude-anthropic/index.mdx`
- `/src/content/docs/pro/integrations/mcp-server/openai-chatgpt/index.mdx`
- `/src/content/docs/pro/integrations/mcp-server/microsoft-copilot-studio/index.mdx`

---

## 13. Files with Time-Sensitive Content

### Changelog Files (2021-2025)
- All files in `/src/content/docs/pro/changelog/` directory
- Contains version-specific updates and feature releases

### Files with "as of 2023" or Version References
- Multiple files containing date-specific or version-specific information that may need updating

---

## Recommendations

1. **Priority Updates Required:**
   - AI service integrations (rapidly evolving field)
   - Authentication providers (security updates)
   - API documentation (version changes)
   - Analytics platforms (feature updates)

2. **Regular Review Schedule:**
   - Quarterly: AI/ML services, API documentation
   - Semi-annually: Analytics platforms, middleware integrations
   - Annually: Authentication providers, business systems

3. **Monitor for:**
   - Service deprecations or sunsets
   - API version changes
   - Pricing model updates
   - New feature releases
   - Security patches or vulnerabilities

4. **Action Items:**
   - Set up monitoring for vendor announcements
   - Create a review calendar for time-sensitive content
   - Establish a process for tracking vendor API changes
   - Document vendor-specific update procedures