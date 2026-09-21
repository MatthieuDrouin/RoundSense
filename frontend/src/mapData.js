const RAW = 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars';

export const MAP_DATA = {
  de_cache: {posX:-2000,posY:3250,scale:5.5,a:[.325,.26],b:[.345,.79]},
  de_mirage: {posX:-3230,posY:1713,scale:5,a:[.54,.76],b:[.23,.28]},
  de_dust2: {posX:-2476,posY:3239,scale:4.4,a:[.80,.16],b:[.21,.12]},
  de_inferno: {posX:-2087,posY:3870,scale:4.9,a:[.81,.69],b:[.49,.22]},
  de_nuke: {posX:-3453,posY:2887,scale:7,a:[.58,.48],b:[.58,.58],lowerZ:-495},
  de_ancient: {posX:-2953,posY:2164,scale:5,a:[.31,.25],b:[.80,.40]},
  de_anubis: {posX:-2796,posY:3328,scale:5.22},
  de_overpass: {posX:-4831,posY:1781,scale:5.2,a:[.55,.23],b:[.70,.31]},
  de_train: {posX:-2477,posY:2392,scale:4.7,a:[.63,.49],b:[.52,.76],lowerZ:-50},
  de_vertigo: {posX:-3168,posY:1762,scale:4,a:[.705,.585],b:[.222,.223],lowerZ:11700},
};

export function radarUrl(mapName, avgZ=null){
  const m=MAP_DATA[mapName];
  if(!m) return null;
  if(m.lowerZ != null && avgZ != null && avgZ < m.lowerZ){
    return `${RAW}/${mapName}_lower_radar_psd.png`;
  }
  return `${RAW}/${mapName}_radar_psd.png`;
}

export function worldToRadar(mapName, x, y){
  const m=MAP_DATA[mapName];
  if(!m || x == null || y == null) return null;

  // Valve overview transform: each radar pixel covers "scale" world units.
  // Radar textures are 1024x1024 and posX/posY are the top-left world origin.
  const px=(Number(x)-m.posX)/m.scale;
  const py=(m.posY-Number(y))/m.scale;

  return {x:px/1024,y:py/1024};
}

// Display coordinates intentionally stay identical to the 1024x1024 radar
// texture coordinates. Do not apply CSS zoom/crop independently or markers
// will no longer line up with the map.
export function toDisplayPoint(_mapName, point){
  return point;
}

export function mapImageStyle(){
  return {};
}

export function onRadar(point){
  return point && point.x >= 0 && point.x <= 1 && point.y >= 0 && point.y <= 1;
}
