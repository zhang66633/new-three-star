// 程序化星球着色器 - 每个世界独特的表面效果
// 使用 simplex noise + domain warping + 主题参数生成

const noiseGLSL = `
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v) {
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod289(i);
  vec4 p = permute(permute(permute(
    i.z + vec4(0.0, i1.z, i2.z, 1.0))
    + i.y + vec4(0.0, i1.y, i2.y, 1.0))
    + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0)*2.0 + 1.0;
  vec4 s1 = floor(b1)*2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}

// FBM with inter-octave rotation (eliminates axis-aligned artifacts)
vec3 rotateOctave(vec3 p) {
  // Fixed rotation matrix (golden angle based) to decorrelate octaves
  float c = 0.7071;
  float s = 0.7071;
  return vec3(
    p.x * c - p.z * s,
    p.y * 0.8 + p.x * 0.36 + p.z * 0.48,
    p.x * s + p.z * c
  );
}

float fbm(vec3 p, int octaves) {
  float value = 0.0;
  float amplitude = 0.5;
  float frequency = 1.0;
  for (int i = 0; i < 6; i++) {
    if (i >= octaves) break;
    value += amplitude * snoise(p * frequency);
    p = rotateOctave(p); // rotate between octaves
    frequency *= 2.0;
    amplitude *= 0.5;
  }
  return value;
}

// Domain warping: feed noise back into coordinates for organic distortion
float warpedFbm(vec3 p, int octaves, float warpStrength) {
  vec3 warp = vec3(
    fbm(p + vec3(0.0, 5.2, 1.3), octaves - 1),
    fbm(p + vec3(5.2, 1.3, 0.0), octaves - 1),
    fbm(p + vec3(1.3, 0.0, 5.2), octaves - 1)
  );
  return fbm(p + warp * warpStrength, octaves);
}
`

export const planetVertexShader = `
varying vec3 vNormal;
varying vec3 vPosition;
varying vec3 vWorldNormal;
varying vec3 vViewDir;
varying vec2 vUv;
void main() {
  vNormal = normalize(normalMatrix * normal);
  vPosition = position;
  vUv = uv;
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vWorldNormal = normalize((modelMatrix * vec4(normal, 0.0)).xyz);
  vViewDir = normalize(cameraPosition - worldPos.xyz);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

// 通用星球片段着色器 - 通过 uniform 控制风格
export const planetFragmentShader = `
uniform float uTime;
uniform vec3 uColor1;
uniform vec3 uColor2;
uniform vec3 uColor3;
uniform float uNoiseScale;
uniform float uNoiseSpeed;
uniform int uOctaves;
uniform float uStyle; // 0=有机 1=glitch 2=水墨 3=能量 4=几何

varying vec3 vNormal;
varying vec3 vPosition;
varying vec3 vWorldNormal;
varying vec3 vViewDir;
varying vec2 vUv;

${noiseGLSL}

void main() {
  vec3 p = vPosition * uNoiseScale;
  float t = uTime * uNoiseSpeed;

  // === Surface noise (style-dependent, with domain warping) ===
  float n;
  if (uStyle < 0.5) {
    // 有机/触手风格 — heavy domain warping for tentacle-like distortion
    n = warpedFbm(p + vec3(t * 0.1, t * 0.05, 0.0), uOctaves, 0.8);
    float tentacle = abs(snoise(p * 2.0 + vec3(0.0, t * 0.2, t * 0.1)));
    tentacle = pow(1.0 - tentacle, 3.0);
    n = n * 0.6 + tentacle * 0.4;
  } else if (uStyle < 1.5) {
    // Glitch风格 — sharp domain warp + scanlines
    n = warpedFbm(p, uOctaves, 0.3);
    float glitch = step(0.92, snoise(vec3(p.y * 20.0, t * 2.0, 0.0)));
    float scanline = sin(vPosition.y * 80.0 + t * 5.0) * 0.5 + 0.5;
    n = mix(n, glitch, scanline * 0.4);
  } else if (uStyle < 2.5) {
    // 水墨/云雾风格 — soft domain warping, wispy
    n = warpedFbm(p + vec3(t * 0.02, 0.0, t * 0.03), uOctaves, 0.6);
    n = smoothstep(-0.2, 0.8, n);
    float wisp = snoise(p * 3.0 + vec3(t * 0.1));
    n = n * 0.7 + wisp * 0.3;
  } else if (uStyle < 3.5) {
    // 能量/元素风格 — moderate warp + energy veins
    n = warpedFbm(p + vec3(0.0, t * 0.15, t * 0.1), uOctaves, 0.4);
    float energy = abs(snoise(p * 4.0 + t * 0.3));
    energy = pow(energy, 2.0);
    n = n * 0.5 + energy * 0.5;
  } else {
    // 几何/秩序风格 — minimal warp + grid overlay
    n = warpedFbm(p, uOctaves, 0.2);
    float grid = abs(sin(vPosition.x * 10.0)) * abs(sin(vPosition.y * 10.0)) * abs(sin(vPosition.z * 10.0));
    n = mix(n, grid, 0.3);
  }

  // === Cloud layer (rotates at different speed, adds depth) ===
  vec3 cloudP = vPosition * uNoiseScale * 1.8;
  float cloud = fbm(cloudP + vec3(t * 0.4, t * 0.1, t * 0.25), max(uOctaves - 2, 2));
  cloud = smoothstep(0.1, 0.7, cloud) * 0.25; // subtle cloud wisps

  // === Three-color mixing ===
  vec3 color;
  if (n < 0.0) {
    color = mix(uColor1, uColor2, n + 1.0);
  } else {
    color = mix(uColor2, uColor3, n);
  }
  // Add cloud highlights
  color = mix(color, uColor3 * 1.3, cloud);

  // === Proper view-dependent Fresnel ===
  float fresnel = 1.0 - max(dot(vViewDir, vWorldNormal), 0.0);
  fresnel = pow(fresnel, 2.5);

  // === Rim glow (bright edges instead of dark) ===
  vec3 rimColor = mix(uColor2, uColor3, 0.5) * 1.5;
  color += rimColor * fresnel * 0.6;

  // === Atmospheric color shift at limb ===
  vec3 atmosColor = uColor2 * 0.5 + vec3(0.1, 0.15, 0.3); // slight blue shift
  color = mix(color, atmosColor, fresnel * 0.3);

  // === Subtle diffuse lighting (top-down) ===
  float diffuse = max(dot(vWorldNormal, normalize(vec3(0.3, 1.0, 0.5))), 0.0);
  color *= 0.55 + diffuse * 0.45;

  gl_FragColor = vec4(color, 1.0);
}
`

// 吸积盘/漩涡着色器
export const vortexVertexShader = `
varying vec2 vUv;
varying vec3 vPosition;
void main() {
  vUv = uv;
  vPosition = position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

export const vortexFragmentShader = `
uniform float uTime;
uniform vec3 uColor;
uniform float uOpacity;

varying vec2 vUv;
varying vec3 vPosition;

${noiseGLSL}

void main() {
  // 极坐标
  vec2 center = vUv - 0.5;
  float dist = length(center) * 2.0;
  float angle = atan(center.y, center.x);

  // 螺旋扭曲
  float spiral = sin(angle * 3.0 + dist * 12.0 - uTime * 1.5) * 0.5 + 0.5;
  float noise = snoise(vec3(center * 4.0, uTime * 0.3)) * 0.5 + 0.5;

  // 径向衰减（内亮外暗）
  float radialFade = smoothstep(1.0, 0.2, dist);
  // 内圈裁切（星球遮挡）
  float innerCut = smoothstep(0.15, 0.35, dist);

  float alpha = spiral * noise * radialFade * innerCut * uOpacity;

  vec3 color = uColor * (0.7 + spiral * 0.3);
  gl_FragColor = vec4(color, alpha);
}
`

// 每个世界的 shader 参数
export interface PlanetShaderParams {
  color1: string
  color2: string
  color3: string
  noiseScale: number
  noiseSpeed: number
  octaves: number
  style: number // 0=有机 1=glitch 2=水墨 3=能量 4=几何
  vortexColor: string
  vortexOpacity: number
}

export const PLANET_SHADER_PARAMS: Record<string, PlanetShaderParams> = {
  cthulhu: {
    color1: '#1a0533', color2: '#4a1a7a', color3: '#2aff8a',
    noiseScale: 2.5, noiseSpeed: 0.15, octaves: 5, style: 0,
    vortexColor: '#6633aa', vortexOpacity: 0.4,
  },
  game_world: {
    color1: '#001a2e', color2: '#00ccff', color3: '#ff00aa',
    noiseScale: 3.0, noiseSpeed: 0.4, octaves: 4, style: 1,
    vortexColor: '#00ddff', vortexOpacity: 0.35,
  },
  murder_mystery: {
    color1: '#1a1000', color2: '#cc8800', color3: '#ffdd66',
    noiseScale: 2.0, noiseSpeed: 0.08, octaves: 4, style: 4,
    vortexColor: '#ddaa33', vortexOpacity: 0.3,
  },
  pokemon: {
    color1: '#330000', color2: '#ff3300', color3: '#ffcc00',
    noiseScale: 3.5, noiseSpeed: 0.25, octaves: 4, style: 3,
    vortexColor: '#ff6622', vortexOpacity: 0.35,
  },
  philosophy: {
    color1: '#0d0020', color2: '#7744cc', color3: '#eeddff',
    noiseScale: 1.8, noiseSpeed: 0.05, octaves: 5, style: 2,
    vortexColor: '#9966dd', vortexOpacity: 0.25,
  },
  cultivation: {
    color1: '#001a0d', color2: '#00aa55', color3: '#ccffee',
    noiseScale: 2.0, noiseSpeed: 0.06, octaves: 5, style: 2,
    vortexColor: '#33ddaa', vortexOpacity: 0.3,
  },
  zhangjiao: {
    color1: '#1a1500', color2: '#ccaa00', color3: '#ffee88',
    noiseScale: 2.2, noiseSpeed: 0.1, octaves: 4, style: 2,
    vortexColor: '#ddcc33', vortexOpacity: 0.3,
  },
  trpg: {
    color1: '#0a0020', color2: '#4433aa', color3: '#8877ff',
    noiseScale: 2.5, noiseSpeed: 0.12, octaves: 5, style: 4,
    vortexColor: '#5544cc', vortexOpacity: 0.35,
  },
  elo: {
    color1: '#001a1a', color2: '#009988', color3: '#66ffdd',
    noiseScale: 2.8, noiseSpeed: 0.15, octaves: 4, style: 4,
    vortexColor: '#22ccaa', vortexOpacity: 0.3,
  },
  create: {
    color1: '#0a0a2a', color2: '#4466cc', color3: '#aaccff',
    noiseScale: 1.5, noiseSpeed: 0.08, octaves: 5, style: 2,
    vortexColor: '#6688dd', vortexOpacity: 0.5,
  },
  tianyi: {
    color1: '#1a0000', color2: '#ff4422', color3: '#ffaa00',
    noiseScale: 3.5, noiseSpeed: 0.5, octaves: 5, style: 3,
    vortexColor: '#ff5533', vortexOpacity: 0.5,
  },
}
