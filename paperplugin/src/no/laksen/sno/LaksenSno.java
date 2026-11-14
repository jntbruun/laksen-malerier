package no.laksen.sno;

import java.time.LocalDate;
import java.util.HashSet;
import java.util.Set;
import org.bukkit.Chunk;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockFormEvent;
import org.bukkit.event.block.EntityBlockFormEvent;
import org.bukkit.event.world.ChunkLoadEvent;
import org.bukkit.plugin.java.JavaPlugin;

/**
 * The laksen-sno datapack makes land biomes cold so rain falls as snow. Vanilla then also freezes
 * exposed water there, and no game rule turns that off. In the biomes listed in config.yml this
 * 1. stops weather from freezing water into ice, and
 * 2. melts ice that weather already made, whenever a chunk loads.
 * Frost Walker and snow golems still work, and ice elsewhere is untouched.
 */
public final class LaksenSno extends JavaPlugin implements Listener {
    private static final BlockFace[] SIDES = {BlockFace.NORTH, BlockFace.SOUTH, BlockFace.EAST, BlockFace.WEST};
    private final Set<String> noFreezeBiomes = new HashSet<>();
    private int melted;
    private boolean meltExisting;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        noFreezeBiomes.addAll(getConfig().getStringList("ingen-frysing"));
        // Melting is a one-off cleanup for ice made before this plugin existed; after the date
        // only new freezing is stopped, so ice that players build later is never touched.
        Object until = getConfig().get("smelt-vaeris-til");
        LocalDate last = until instanceof java.util.Date d
                ? d.toInstant().atZone(java.time.ZoneId.systemDefault()).toLocalDate()   // YAML read an unquoted date
                : until == null || until.toString().isBlank() ? null : LocalDate.parse(until.toString().trim());
        meltExisting = last != null && !LocalDate.now().isAfter(last);
        getServer().getPluginManager().registerEvents(this, this);
        if (meltExisting) {
            for (World world : getServer().getWorlds()) {
                for (Chunk chunk : world.getLoadedChunks()) meltWeatherIce(chunk);
            }
        }
        getLogger().info("Vann fryser ikke i " + noFreezeBiomes.size() + " biomer." + (meltExisting ? " Smelter værfrosset is ved lasting av chunks (smeltet " + melted + " så langt)." : ""));
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onWeatherFreeze(BlockFormEvent event) {
        if (event instanceof EntityBlockFormEvent) return;
        if (event.getNewState().getType() != Material.ICE) return;
        if (event.getBlock().getType() != Material.WATER) return;
        if (inNoFreezeBiome(event.getBlock())) event.setCancelled(true);
    }

    @EventHandler
    public void onChunkLoad(ChunkLoadEvent event) {
        // World generation still freezes our biomes where a chunk also holds a vanilla biome,
        // so brand-new chunks are always cleaned. Old chunks only until the date in config.yml.
        if (event.isNewChunk() || meltExisting) meltWeatherIce(event.getChunk());
    }

    private boolean inNoFreezeBiome(Block block) {
        return noFreezeBiomes.contains(block.getBiome().getKey().toString());
    }

    /**
     * Weather ice is always the top block of its column and sits on or next to water.
     * Ice that isn't (player builds, ice under a roof) is left alone.
     */
    private void meltWeatherIce(Chunk chunk) {
        if (chunk.getWorld().getEnvironment() != World.Environment.NORMAL) return;
        World world = chunk.getWorld();
        int baseX = chunk.getX() << 4, baseZ = chunk.getZ() << 4;
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                Block top = world.getHighestBlockAt(baseX + dx, baseZ + dz);
                if (top.getType() != Material.ICE || !inNoFreezeBiome(top)) continue;
                if (!touchesWater(top)) continue;
                top.setType(Material.WATER, false);
                melted++;
            }
        }
    }

    private static boolean touchesWater(Block ice) {
        if (ice.getRelative(BlockFace.DOWN).getType() == Material.WATER) return true;
        for (BlockFace side : SIDES) {
            Material m = ice.getRelative(side).getType();
            if (m == Material.WATER || m == Material.ICE) return true;
        }
        return false;
    }
}
