// Плёночный грейд: зерно, виньетка, лёгкая хроматическая аберрация, общий фейд.
export const FilmGrade = {
  uniforms: { tDiffuse: { value: null }, uTime: { value: 0 }, uFade: { value: 1 } },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse; uniform float uTime; uniform float uFade; varying vec2 vUv;
    float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)))*43758.5453); }
    void main(){
      vec2 c = vUv - 0.5;
      float d = dot(c,c);
      vec2 off = c * d * 0.012;
      vec3 col = vec3(texture2D(tDiffuse, vUv+off).r, texture2D(tDiffuse, vUv).g, texture2D(tDiffuse, vUv-off).b);
      col = mix(col, col*vec3(1.04,1.0,0.94), 0.6);           // тёплый хайлайт
      col += vec3(0.0,0.006,0.012) * (1.0-col);                 // холодные тени
      col *= smoothstep(0.95, 0.15, d*1.6);                     // виньетка
      float n = h(vUv*vec2(1280.,720.) + mod(uTime,97.)*13.1) - 0.5;
      col += n * 0.035;
      gl_FragColor = vec4(col * uFade, 1.0);
    }`
};
