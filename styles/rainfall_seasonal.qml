<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.2.2-Bonn" maxScale="0" minScale="1e+8" hasScaleBasedVisibilityFlag="0">
  <pipe>
    <rasterrenderer opacity="1" classificationMax="inf" type="singlebandpseudocolor" band="1" alphaBand="-1" classificationMin="10">
      <rasterTransparency/>
      <minMaxOrigin>
        <limits>None</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <rastershader>
        <colorrampshader classificationMode="2" colorRampType="DISCRETE" clip="0">
          <colorramp type="gradient" name="[source]">
            <prop k="color1" v="215,25,28,255"/>
            <prop k="color2" v="43,131,186,255"/>
            <prop k="discrete" v="0"/>
            <prop k="rampType" v="gradient"/>
            <prop k="stops" v="0.25;253,174,97,255:0.5;255,255,191,255:0.75;171,221,164,255"/>
          </colorramp>
          <item color="#ffffff" alpha="255" label="  0-10mm" value="10"/>
          <item color="#f2f2f2" alpha="255" label=" 11- 20" value="20"/>
          <item color="#d5d5d5" alpha="255" label="21-40mm" value="40"/>
          <item color="#f1f1c1" alpha="255" label="41-50mm" value="50"/>
          <item color="#fafa7c" alpha="255" label="51-60mm" value="60"/>
          <item color="#ffff00" alpha="255" label="61-80mm" value="80"/>
          <item color="#aaff55" alpha="255" label="81-100mm" value="100"/>
          <item color="#57ff57" alpha="255" label="101-125mm" value="125"/>
          <item color="#02ff00" alpha="255" label="126-150mm" value="150"/>
          <item color="#0ffab8" alpha="255" label="151-175mm" value="175"/>
          <item color="#00fffb" alpha="255" label="176-200mm" value="200"/>
          <item color="#0fd3fa" alpha="255" label="201-250mm" value="250"/>
          <item color="#00aeff" alpha="255" label="251-300mm" value="300"/>
          <item color="#007bff" alpha="255" label="301-350mm" value="350"/>
          <item color="#130fff" alpha="255" label="251-400mm" value="400"/>
          <item color="#f273e4" alpha="255" label="401-500mm" value="500"/>
          <item color="#9e15f2" alpha="255" label="501-600mm" value="600"/>
          <item color="#841f89" alpha="255" label="601-800mm" value="800"/>
          <item color="#57145b" alpha="255" label=">800mm" value="inf"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0"/>
    <huesaturation saturation="0" colorizeBlue="128" colorizeRed="255" colorizeOn="0" colorizeStrength="100" grayscaleMode="0" colorizeGreen="128"/>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
