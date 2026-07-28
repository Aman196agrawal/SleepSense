const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Disable package.json `exports` field resolution so Metro uses CJS builds
// instead of ESM builds that contain `import.meta` syntax, which browsers
// reject outside native ES modules.
config.resolver.unstable_enablePackageExports = false;

// Metro defaults to (cores - 1) transform workers — 11 on this 12-core dev
// machine. Each worker is a full Node process running Babel, which on a 7.3GB
// host exhausts RAM and kills the bundle near 100% with a misleading
// "UNKNOWN: unknown error, open <some babel plugin>" (the Win32 out-of-resources
// code has no libuv mapping). Capping the pool keeps bundling survivable.
config.maxWorkers = 2;

module.exports = config;
