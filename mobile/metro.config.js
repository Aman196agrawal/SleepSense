const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Disable package.json `exports` field resolution so Metro uses CJS builds
// instead of ESM builds that contain `import.meta` syntax, which browsers
// reject outside native ES modules.
config.resolver.unstable_enablePackageExports = false;

module.exports = config;
