<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis maxScale="0" version="3.6.0-Noosa" minScale="1e+08" styleCategories="AllStyleCategories" hasScaleBasedVisibilityFlag="0">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
  </flags>
  <customproperties>
    <property value="false" key="WMSBackgroundLayer"/>
    <property value="false" key="WMSPublishDataSourceUrl"/>
    <property value="0" key="embeddedWidgets/count"/>
    <property value="Value" key="identify/format"/>
  </customproperties>
  <pipe>
    <rasterrenderer type="singlebandpseudocolor" opacity="1" band="1" classificationMin="0" alphaBand="-1" classificationMax="1000">
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
          <item value="0" alpha="240" color="#ffffff" label="0"/>
          <item value="5" alpha="255" color="#eac23e" label="1-5mm"/>
          <item value="10" alpha="255" color="#ecda0d" label="5-10mm"/>
          <item value="15" alpha="255" color="#e0f637" label="10-15mm"/>
          <item value="20" alpha="255" color="#eaff00" label="15-20mm"/>
          <item value="25" alpha="255" color="#8dfd55" label="20-25mm"/>
          <item value="30" alpha="255" color="#00ff00" label="25-30mm"/>
          <item value="50" alpha="255" color="#10faf7" label="30-50mm"/>
          <item value="75" alpha="255" color="#0f17ff" label="50-75mm"/>
          <item value="150" alpha="255" color="#f273e4" label="75-150mm"/>
          <item value="225" alpha="255" color="#841f89" label="250-225mm"/>
          <item value="1000" alpha="255" color="#c21664" label="225-1000mm"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0"/>
    <huesaturation saturation="0" colorizeRed="255" colorizeBlue="128" colorizeGreen="128" colorizeOn="0" colorizeStrength="100" grayscaleMode="0"/>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
