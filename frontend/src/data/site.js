// App-wide constants and copy. Content lives here, not in components.
export const site = {
  name: "Scraply",
  version: "v2.0",
  company: "Nicky Tools",
  year: 2026,
  target: "company.info",
};

export const auth = {
  login: {
    headline: "Scrape company contacts on autopilot.",
    lead:
      "Upload a CSV of companies and Scraply pulls phone numbers, emails, business and owner names straight from company.info - at scale.",
    features: [
      { icon: "csv", text: "Bulk CSV input with smart column mapping" },
      { icon: "bolt", text: "Live job progress, pause & resume" },
      { icon: "download", text: "One-click enriched CSV export" },
    ],
  },
  register: {
    headline: "Join the automation platform.",
    lead:
      "Accounts are admin-managed. Register with the admin secret key provided by your administrator to get access to the Scraply workspace.",
    features: [
      { icon: "lock", text: "Secure, key-gated registration" },
      { icon: "shield", text: "Role-based access to every tool" },
      { icon: "globe", text: "Your data stays in your workspace" },
    ],
  },
};

// The four fields the scraper needs from the uploaded file, in mapping order.
export const MAPPING_STEPS = [
  { key: "col_company", question: "Which column is the Business Name?" },
  { key: "col_street", question: "Which column is the Street Name?" },
  { key: "col_house_number", question: "Which column is the House Number?" },
  { key: "col_city", question: "Which column is the Place / City?" },
];
