import next from "eslint-config-next/core-web-vitals";

const config = [
  { ignores: [".next/**", "out/**", "dist/**", "node_modules/**"] },
  ...next,
];

export default config;
