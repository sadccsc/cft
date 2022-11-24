<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis hasScaleBasedVisibilityFlag="0" maxScale="0" minScale="1e+08" styleCategories="AllStyleCategories" version="3.14.1-Pi">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
  </flags>
  <temporal fetchMode="0" enabled="0" mode="0">
    <fixedRange>
      <start></start>
      <end></end>
    </fixedRange>
  </temporal>
  <customproperties>
    <property key="WMSBackgroundLayer" value="false"/>
    <property key="WMSPublishDataSourceUrl" value="false"/>
    <property key="embeddedWidgets/count" value="0"/>
    <property key="identify/format" value="Value"/>
  </customproperties>
  <pipe>
    <rasterrenderer alphaBand="-1" band="1" type="singlebandpseudocolor" nodataColor="" opacity="1" classificationMin="0" classificationMax="400">
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
        <colorrampshader colorRampType="DISCRETE" classificationMode="1" clip="0" minimumValue="0" maximumValue="400">
          <colorramp type="gradient" name="[source]">
            <prop k="color1" v="247,251,255,255"/>
            <prop k="color2" v="8,48,107,255"/>
            <prop k="discrete" v="0"/>
            <prop k="rampType" v="gradient"/>
            <prop k="stops" v="0.13;222,235,247,255:0.26;198,219,239,255:0.39;158,202,225,255:0.52;107,174,214,255:0.65;66,146,198,255:0.78;33,113,181,255:0.9;8,81,156,255"/>
          </colorramp>
          <item alpha="0" label="No Forecast" color="#ffffff" value="0"/>
          <item alpha="255" label="50" color="#dfc9ae" value="50"/>
          <item alpha="255" label="60" color="#d6ba97" value="60"/>
          <item alpha="255" label="70" color="#bda17e" value="70"/>
          <item alpha="255" label="80" color="#937d62" value="80"/>
          <item alpha="255" label="100" color="#695946" value="100"/>
          <item alpha="255" label="50" color="#feffcc" value="150"/>
          <item alpha="255" label="60" color="#fdffb3" value="160"/>
          <item alpha="255" label="70" color="#fdff81" value="170"/>
          <item alpha="255" label="80" color="#fbff03" value="180"/>
          <item alpha="255" label="100" color="#e1e502" value="200"/>
          <item alpha="255" label="50" color="#cefffe" value="250"/>
          <item alpha="255" label="60" color="#9dfffd" value="260"/>
          <item alpha="255" label="70" color="#6cfffc" value="270"/>
          <item alpha="255" label="80" color="#3bfffb" value="280"/>
          <item alpha="255" label="100" color="#0bfffb" value="300"/>
          <item alpha="255" label="50" color="#d0ccfe" value="350"/>
          <item alpha="255" label="60" color="#a199fd" value="360"/>
          <item alpha="255" label="70" color="#7366fd" value="370"/>
          <item alpha="255" label="80" color="#2d1afc" value="380"/>
          <item alpha="255" label="100" color="#1300e2" value="400"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0"/>
    <huesaturation saturation="0" colorizeOn="0" colorizeGreen="128" colorizeRed="255" grayscaleMode="0" colorizeBlue="128" colorizeStrength="100"/>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
