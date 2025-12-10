import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';

const UploadScreen = () => {
  const navigation = useNavigation();

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.eyebrow}>Step 02</Text>
        <Text style={styles.title}>Upload Photo</Text>
        <Text style={styles.description}>
          Placeholder screen for the gallery picker. Drop in your favorite selfie, a backstage photo, or
          a makeup-free snap. The Allume stylist engine will validate clarity and guide you through any
          touch-ups before building your personalized lookbook.
        </Text>
        <TouchableOpacity style={styles.secondaryButton} onPress={() => navigation.navigate('Capture')}>
          <Text style={styles.secondaryLabel}>Need to capture a fresh selfie?</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={styles.link} onPress={() => navigation.goBack()}>
        <Text style={styles.linkText}>Back to onboarding</Text>
      </TouchableOpacity>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff8fb',
    padding: 24,
    justifyContent: 'center',
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 24,
    padding: 24,
    shadowColor: '#f48fb1',
    shadowOpacity: 0.2,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 10 },
    elevation: 4,
  },
  eyebrow: {
    textTransform: 'uppercase',
    letterSpacing: 1,
    fontSize: 12,
    fontWeight: '600',
    color: '#c2185b',
  },
  title: {
    fontSize: 26,
    fontWeight: '700',
    marginTop: 8,
    color: '#54133d',
  },
  description: {
    marginTop: 12,
    color: '#7a4763',
    lineHeight: 20,
  },
  secondaryButton: {
    marginTop: 20,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#f8b7d5',
    paddingVertical: 14,
    paddingHorizontal: 18,
    backgroundColor: '#fff6fb',
  },
  secondaryLabel: {
    color: '#b1035a',
    textAlign: 'center',
    fontWeight: '600',
  },
  link: {
    marginTop: 18,
    alignSelf: 'center',
  },
  linkText: {
    color: '#c2185b',
    fontWeight: '600',
  },
});

export default UploadScreen;
