import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import HomeScreen from '../screens/HomeScreen';
import CaptureScreen from '../screens/CaptureScreen';
import UploadScreen from '../screens/UploadScreen';

const Stack = createNativeStackNavigator();

const RootNavigator = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShadowVisible: false,
        headerTintColor: '#b83280',
        headerTitleStyle: { fontWeight: '600', color: '#5c2256' },
        contentStyle: { backgroundColor: '#fff8fb' },
      }}
    >
      <Stack.Screen name="Home" component={HomeScreen} options={{ headerShown: false }} />
      <Stack.Screen name="Capture" component={CaptureScreen} options={{ title: 'Capture Selfie' }} />
      <Stack.Screen name="Upload" component={UploadScreen} options={{ title: 'Upload Photo' }} />
    </Stack.Navigator>
  );
};

export default RootNavigator;
