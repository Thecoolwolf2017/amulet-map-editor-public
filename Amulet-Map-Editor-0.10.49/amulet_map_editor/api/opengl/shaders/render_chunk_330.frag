#version 330
in vec2 fTexCoord;
in vec4 fTexOffset;
in vec3 fTint;

out vec4 outColor;

uniform sampler2D image;

void main(){
    vec4 texColor = texture(
    	image,
    	vec2(
			mix(fTexOffset.x, fTexOffset.z, mod(fTexCoord.x, 1.0)),
			mix(fTexOffset.y, fTexOffset.w, mod(fTexCoord.y, 1.0))
		)
	);
	if(texColor.a < 0.02)
        discard;
    vec3 tint = fTint;
    // minecraft_model_reader may emit a pure-green sentinel tint for biome
    // foliage when no biome colour sampling is available. Use a stable fallback.
    if (tint.r <= 0.001 && tint.g >= 0.999 && tint.b <= 0.001) {
        tint = vec3(0.58, 0.74, 0.36);
    }
    texColor.xyz = texColor.xyz * tint * 0.85;
	outColor = texColor;
}
