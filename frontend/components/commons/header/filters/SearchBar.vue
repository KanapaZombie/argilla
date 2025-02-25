<!--
  - coding=utf-8
  - Copyright 2021-present, the Recognai S.L. team.
  -
  - Licensed under the Apache License, Version 2.0 (the "License");
  - you may not use this file except in compliance with the License.
  - You may obtain a copy of the License at
  -
  -     http://www.apache.org/licenses/LICENSE-2.0
  -
  - Unless required by applicable law or agreed to in writing, software
  - distributed under the License is distributed on an "AS IS" BASIS,
  - WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  - See the License for the specific language governing permissions and
  - limitations under the License.
  -->

<template>
  <form @submit.prevent="submit(query)">
    <div :class="['searchbar__container', { active: query }]">
      <base-input-container class="searchbar">
        <svgicon
          v-if="!query && !dataset.query.text"
          name="search"
          width="20"
          height="40"
        />
        <svgicon
          v-else
          class="searchbar__button"
          name="close"
          width="20"
          height="20"
          @click="removeFilter()"
        />
        <base-input
          ref="input"
          v-model="query"
          class="searchbar__input"
          placeholder="Introduce a query"
        />
      </base-input-container>
    </div>
  </form>
</template>

<script>
import "assets/icons/close";
import "assets/icons/search";

export default {
  props: {
    dataset: {
      type: Object,
      required: true,
    },
    expandSearchbar: {
      type: Boolean,
    },
  },
  data: () => ({
    queryText: null,
  }),
  computed: {
    query: {
      get() {
        return this.queryText === null
          ? this.dataset.query.text
          : this.queryText;
      },
      set(val) {
        this.queryText = val;
      },
    },
  },
  methods: {
    submit(query) {
      this.$refs.input.$el.blur();
      this.$emit("submit", query);
    },
    removeFilter() {
      this.query = "";
      this.$emit("submit", this.query);
    },
  },
};
</script>

<style lang="scss" scoped>
.searchbar {
  background: palette(white);
  width: 285px;
  min-height: 43px;
  border: none;
  display: flex;
  align-items: center;
  transition: all 0.2s ease;
  margin-right: 0;
  margin-left: auto;
  pointer-events: all;
  border-radius: $border-radius-s;
  min-width: 100%;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.13);
  &__container {
    position: relative;
    margin-right: auto;
    margin-left: 0;
    min-width: 100%;
  }
  &__button {
    cursor: pointer;
    padding: 5px;
    border-radius: $border-radius-s;
    background: palette(white);
    transition: background 0.2s ease-in-out;
    &:hover {
      transition: background 0.2s ease-in-out;
      background: palette(grey, 800);
    }
  }
  .svg-icon {
    fill: $black-54;
    margin: auto 1em auto 1em;
  }
  &:hover {
    box-shadow: $shadow;
  }
}
</style>
