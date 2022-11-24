<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis minScale="1e+08" hasScaleBasedVisibilityFlag="0" maxScale="0" version="3.22.2-Białowieża" styleCategories="AllStyleCategories">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
    <Private>0</Private>
  </flags>
  <temporal fetchMode="0" enabled="0" mode="0">
    <fixedRange>
      <start></start>
      <end></end>
    </fixedRange>
  </temporal>
  <customproperties>
    <Option type="Map">
      <Option name="WMSBackgroundLayer" type="bool" value="false"/>
      <Option name="WMSPublishDataSourceUrl" type="bool" value="false"/>
      <Option name="embeddedWidgets/count" type="QString" value="0"/>
      <Option name="variableNames"/>
      <Option name="variableValues"/>
    </Option>
  </customproperties>
  <pipe-data-defined-properties>
    <Option type="Map">
      <Option name="name" type="QString" value=""/>
      <Option name="properties"/>
      <Option name="type" type="QString" value="collection"/>
    </Option>
  </pipe-data-defined-properties>
  <pipe>
    <provider>
      <resampling enabled="false" zoomedInResamplingMethod="nearestNeighbour" maxOversampling="2" zoomedOutResamplingMethod="nearestNeighbour"/>
    </provider>
    <rasterrenderer classificationMin="0" alphaBand="-1" band="1" type="singlebandpseudocolor" nodataColor="" classificationMax="400" opacity="1">
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
        <colorrampshader labelPrecision="0" clip="0" minimumValue="0" classificationMode="1" colorRampType="DISCRETE" maximumValue="400">
          <colorramp name="[source]" type="gradient">
            <Option type="Map">
              <Option name="color1" type="QString" value="255,255,255,0"/>
              <Option name="color2" type="QString" value="22,1,252,255"/>
              <Option name="discrete" type="QString" value="0"/>
              <Option name="rampType" type="QString" value="gradient"/>
              <Option name="stops" type="QString" value="0.0025;210,180,140,255:0.005;251,255,3,255:0.0075;11,255,251,255:0.01;22,1,252,255"/>
            </Option>
            <prop v="255,255,255,0" k="color1"/>
            <prop v="22,1,252,255" k="color2"/>
            <prop v="0" k="discrete"/>
            <prop v="gradient" k="rampType"/>
            <prop v="0.0025;210,180,140,255:0.005;251,255,3,255:0.0075;11,255,251,255:0.01;22,1,252,255" k="stops"/>
          </colorramp>
          <item alpha="0" value="0" label="No Forecast" color="#ffffff"/>
          <item alpha="255" value="1" label="Below-Normal to Normal Rainfall" color="#d2b48c"/>
          <item alpha="255" value="2" label="Normal to Below-Normal Rainfall" color="#fbff03"/>
          <item alpha="255" value="3" label="Normal to Above-Normal Rainfall" color="#0bfffb"/>
          <item alpha="255" value="4" label="Above-Normal to Normal Rainfall" color="#1601fc"/>
          <rampLegendSettings orientation="2" maximumLabel="" prefix="" minimumLabel="" useContinuousLegend="1" direction="0" suffix="">
            <numericFormat id="basic">
              <Option type="Map">
                <Option name="decimal_separator" type="QChar" value=""/>
                <Option name="decimals" type="int" value="6"/>
                <Option name="rounding_type" type="int" value="0"/>
                <Option name="show_plus" type="bool" value="false"/>
                <Option name="show_thousand_separator" type="bool" value="true"/>
                <Option name="show_trailing_zeros" type="bool" value="false"/>
                <Option name="thousand_separator" type="QChar" value=""/>
              </Option>
            </numericFormat>
          </rampLegendSettings>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" gamma="1" contrast="0"/>
    <huesaturation invertColors="0" colorizeBlue="128" grayscaleMode="0" saturation="0" colorizeOn="0" colorizeGreen="128" colorizeRed="255" colorizeStrength="100"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
