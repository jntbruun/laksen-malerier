package no.laksen.stonecutter.mixin;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;
import net.minecraft.client.gui.screens.inventory.StonecutterScreen;
import net.minecraft.client.input.KeyEvent;
import net.minecraft.client.multiplayer.MultiPlayerGameMode;
import net.minecraft.core.Holder;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.util.context.ContextMap;
import net.minecraft.world.entity.decoration.painting.PaintingVariant;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.StonecutterMenu;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.SelectableRecipe;
import net.minecraft.world.item.crafting.StonecutterRecipe;
import net.minecraft.world.item.crafting.display.SlotDisplayContext;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Two fixes for picking from a long list of paintings:
 *
 * 1. Vanilla scrolls the list back to the top every time the input slot changes, including when
 *    you take a result or the server resyncs the slot. Here it only resets for a different item.
 *
 * 2. A search box above the stonecutter. The screen is shown a filtered list, and clicks are
 *    translated back to the real recipe index, so the server never sees anything unusual.
 *    Paintings match on title and artist (which includes the year), everything else on its name.
 */
@Mixin(StonecutterScreen.class)
public abstract class StonecutterScreenMixin extends AbstractContainerScreen<StonecutterMenu> {
    @Shadow private float scrollOffs;
    @Shadow private int startIndex;
    @Shadow private boolean displayRecipes;

    @Unique private Item laksen$lastItem;
    @Unique private float laksen$savedScrollOffs;
    @Unique private int laksen$savedStartIndex;
    @Unique private boolean laksen$restoreAfterEmpty;

    @Unique private EditBox laksen$search;
    @Unique private SelectableRecipe.SingleInputSet<StonecutterRecipe> laksen$filteredFrom;
    @Unique private String laksen$filteredQuery = "";
    @Unique private SelectableRecipe.SingleInputSet<StonecutterRecipe> laksen$filtered;
    @Unique private final List<Integer> laksen$realIndex = new ArrayList<>();

    private StonecutterScreenMixin(StonecutterMenu menu, Inventory inventory, Component title) {
        super(menu, inventory, title);
    }

    // ---- 1. Keep the scroll position ------------------------------------------------------------

    @Inject(method = "containerChanged", at = @At("HEAD"), cancellable = true)
    private void laksen$keepScrollPosition(CallbackInfo ci) {
        ItemStack input = this.menu.getSlot(0).getItem();

        if (input.isEmpty()) {
            // Took the last one: remember where we were, in case the same item goes back in.
            if (displayRecipes) {
                laksen$savedScrollOffs = scrollOffs;
                laksen$savedStartIndex = startIndex;
                laksen$restoreAfterEmpty = true;
            }
            return; // vanilla hides the list
        }

        if (input.getItem() == laksen$lastItem) {
            displayRecipes = true;
            if (laksen$restoreAfterEmpty) {
                scrollOffs = laksen$savedScrollOffs;
                startIndex = laksen$savedStartIndex;
                laksen$restoreAfterEmpty = false;
            }
            ci.cancel();
            return;
        }

        // A different item: different recipes, so starting from the top is right.
        laksen$lastItem = input.getItem();
        laksen$restoreAfterEmpty = false;
    }

    // ---- 2. Search ------------------------------------------------------------------------------

    @Override
    protected void init() {
        super.init();
        String previous = laksen$search == null ? "" : laksen$search.getValue();
        laksen$search = new EditBox(this.font, this.leftPos + 52, this.topPos - 14, 76, 12, Component.literal("Søk"));
        laksen$search.setHint(Component.literal("Søk..."));
        laksen$search.setMaxLength(50);
        laksen$search.setValue(previous);
        laksen$search.setResponder(query -> {
            scrollOffs = 0;
            startIndex = 0;
        });
        this.addRenderableWidget(laksen$search);
    }

    @Override
    public boolean keyPressed(KeyEvent event) {
        // While typing, letters like E must go to the box instead of closing the screen.
        if (laksen$search != null && laksen$search.isFocused() && event.key() != 256) {
            laksen$search.keyPressed(event);
            return true;
        }
        return super.keyPressed(event);
    }

    @Unique
    private SelectableRecipe.SingleInputSet<StonecutterRecipe> laksen$view() {
        SelectableRecipe.SingleInputSet<StonecutterRecipe> all = this.menu.getVisibleRecipes();
        String query = laksen$search == null ? "" : laksen$search.getValue().trim().toLowerCase(Locale.ROOT);
        if (query.isEmpty()) {
            return all;
        }
        if (all != laksen$filteredFrom || !query.equals(laksen$filteredQuery)) {
            laksen$filteredFrom = all;
            laksen$filteredQuery = query;
            laksen$realIndex.clear();
            List<SelectableRecipe.SingleInputEntry<StonecutterRecipe>> kept = new ArrayList<>();
            ContextMap context = SlotDisplayContext.fromLevel(Minecraft.getInstance().level);
            String[] words = query.split("\\s+");
            List<SelectableRecipe.SingleInputEntry<StonecutterRecipe>> entries = all.entries();
            for (int i = 0; i < entries.size(); i++) {
                ItemStack result = entries.get(i).recipe().optionDisplay().resolveForFirstStack(context);
                String text = laksen$searchText(result);
                boolean matches = true;
                for (String word : words) {
                    if (!text.contains(word)) {
                        matches = false;
                        break;
                    }
                }
                if (matches) {
                    kept.add(entries.get(i));
                    laksen$realIndex.add(i);
                }
            }
            laksen$filtered = new SelectableRecipe.SingleInputSet<>(kept);
        }
        return laksen$filtered;
    }

    @Unique
    private static String laksen$searchText(ItemStack stack) {
        StringBuilder text = new StringBuilder(stack.getHoverName().getString());
        Holder<PaintingVariant> painting = stack.get(DataComponents.PAINTING_VARIANT);
        if (painting != null) {
            painting.value().title().ifPresent(title -> text.append(' ').append(title.getString()));
            painting.value().author().ifPresent(author -> text.append(' ').append(author.getString()));
        }
        return text.toString().toLowerCase(Locale.ROOT);
    }

    @Unique
    private int laksen$toReal(int shown) {
        if (laksen$view() == this.menu.getVisibleRecipes()) {
            return shown;
        }
        return shown >= 0 && shown < laksen$realIndex.size() ? laksen$realIndex.get(shown) : -1;
    }

    @Unique
    private int laksen$toShown(int real) {
        if (laksen$view() == this.menu.getVisibleRecipes()) {
            return real;
        }
        return laksen$realIndex.indexOf(real);
    }

    @Redirect(method = {"extractRecipes", "extractTooltip"}, at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/inventory/StonecutterMenu;getVisibleRecipes()Lnet/minecraft/world/item/crafting/SelectableRecipe$SingleInputSet;"))
    private SelectableRecipe.SingleInputSet<StonecutterRecipe> laksen$filteredRecipes(StonecutterMenu menu) {
        return laksen$view();
    }

    @Redirect(method = {"isScrollBarActive", "extractButtons", "getOffscreenRows"}, at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/inventory/StonecutterMenu;getNumberOfVisibleRecipes()I"))
    private int laksen$filteredCount(StonecutterMenu menu) {
        return laksen$view().size();
    }

    @Redirect(method = "extractButtons", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/inventory/StonecutterMenu;getSelectedRecipeIndex()I"))
    private int laksen$selectedInView(StonecutterMenu menu) {
        int real = menu.getSelectedRecipeIndex();
        return real < 0 ? real : laksen$toShown(real);
    }

    @Redirect(method = "mouseClicked", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/inventory/StonecutterMenu;clickMenuButton(Lnet/minecraft/world/entity/player/Player;I)Z"))
    private boolean laksen$clickReal(StonecutterMenu menu, Player player, int shown) {
        int real = laksen$toReal(shown);
        return real >= 0 && menu.clickMenuButton(player, real);
    }

    @Redirect(method = "mouseClicked", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/client/multiplayer/MultiPlayerGameMode;handleInventoryButtonClick(II)V"))
    private void laksen$sendReal(MultiPlayerGameMode gameMode, int containerId, int shown) {
        gameMode.handleInventoryButtonClick(containerId, laksen$toReal(shown));
    }
}
